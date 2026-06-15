#!/usr/bin/env bash
set -euo pipefail

PACKAGES=(
    qemu-guest-agent
    cloud-init
    htop
    iotop
    ncdu
    curl
    wget
    vim
    ca-certificates
    chrony
    sudo
    dnsutils
    net-tools
)

echo "==> Updating package cache"
apt-get update

echo "==> Installing missing packages only"
for pkg in "${PACKAGES[@]}"; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
        echo "Already installed: $pkg"
    else
        echo "Installing: $pkg"
        apt-get install -y "$pkg"
    fi
done

echo "==> Full upgrade"
apt-get full-upgrade -y

echo "==> Cleaning apt"
apt-get autoremove -y
apt-get autoclean -y
apt-get clean -y

echo "==> Enabling qemu guest agent"
systemctl enable qemu-guest-agent || true

echo "==> Cleaning cloud-init"
if command -v cloud-init >/dev/null 2>&1; then
    cloud-init clean --logs
fi

echo "==> Removing SSH host keys"
rm -f /etc/ssh/ssh_host_*

echo "==> Resetting machine-id"
truncate -s 0 /etc/machine-id
rm -f /var/lib/dbus/machine-id
ln -sf /etc/machine-id /var/lib/dbus/machine-id

echo "==> Cleaning logs"
find /var/log -type f -exec truncate -s 0 {} \;
find /var/log -type f \( -name "*.gz" -o -name "*.1" -o -name "*.old" \) -delete

echo "==> Cleaning temporary files"
rm -rf /tmp/*
rm -rf /var/tmp/*

echo "==> Cleaning shell history"
unset HISTFILE
rm -f /root/.bash_history
find /home -name ".bash_history" -type f -delete

echo "==> Cleaning user caches"
rm -rf /root/.cache/*
find /home -mindepth 2 -maxdepth 2 -name ".cache" -type d -exec rm -rf {} + 2>/dev/null || true

echo "==> Removing persistent network rules"
rm -f /etc/udev/rules.d/70-persistent-net.rules

echo "==> Setting hostname to template"
hostnamectl set-hostname template

echo "==> Running fstrim"
fstrim -av || true

echo "==> Zero-filling free space"
dd if=/dev/zero of=/EMPTY bs=1M status=progress || true
rm -f /EMPTY
sync

echo "==> Final filesystem trim"
fstrim -av || true

echo
echo "Template cleanup complete."
echo "Now shut down:"

shutdown -h now
