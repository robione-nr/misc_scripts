# Certbot ntfy Deploy Hook

Small Certbot deploy hook that reloads certificate-dependent services after TLS certificate renewal and sends an ntfy notification regarding the status of the operation. Adjust systemd services as needed. This is for my email and webserver.

## Install ntfy Binary

Official Linux binary for amd64 (June 2026):

```bash
wget https://github.com/binwiederhier/ntfy/releases/download/v2.24.0/ntfy_2.24.0_linux_amd64.tar.gz
tar zxvf ntfy_2.24.0_linux_amd64.tar.gz
sudo cp -a ntfy_2.24.0_linux_amd64/ntfy /usr/local/bin/ntfy
```

## Install Hook

Edit the topic first:

```bash
TOPIC_URL="https://ntfy.sh/***YOUR*CHANNEL***"
```

Then install into Certbot's deploy hook directory:

```bash
sudo cp certbot-ntfy-deploy-hook.sh /etc/letsencrypt/renewal-hooks/deploy/certbot-ntfy-deploy-hook
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/certbot-ntfy-deploy-hook
```

Certbot runs deploy hooks after a certificate is successfully renewed.

## Test

Run a dry renewal:

```bash
sudo certbot renew --dry-run
```

Or run the hook directly:

```bash
sudo RENEWED_DOMAINS="example.com" /etc/letsencrypt/renewal-hooks/deploy/certbot-ntfy-deploy-hook
```

[Back to Misc Scripts](../README.md)
