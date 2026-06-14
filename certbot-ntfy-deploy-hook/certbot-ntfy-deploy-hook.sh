#!/bin/bash
set -euo pipefail

TOPIC_URL="https://ntfy.sh/***YOUR*CHANNEL***"
DOMAIN="${RENEWED_DOMAINS%% *}"
DOMAIN="${DOMAIN:-unknown}"
SERVICES=(postfix dovecot apache2)

send_ntfy() {
    local title="$1"
    local priority="$2"
    local tags="$3"
    local message="$4"

    curl -fsS \
        -H "Title: $title" \
        -H "Priority: $priority" \
        -H "Tags: $tags" \
        -d "$message" \
        "$TOPIC_URL"
}

reloaded=()
skipped=()

for svc in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc"; then
        if systemctl reload "$svc"; then
            reloaded+=("$svc")
        else
            msg="Certbot deploy hook FAILED while reloading service for $DOMAIN: $svc"
            send_ntfy "Certbot reload FAILED" "urgent" "rotating_light,warning" "$msg"
            exit 1
        fi
    else
        skipped+=("$svc")
    fi
done

success_msg="Certbot deploy hook succeeded.
Domain: $DOMAIN
Reloaded: ${reloaded[*]:-none}
Skipped: ${skipped[*]:-none}"

send_ntfy "Certbot reload OK" "default" "white_check_mark,lock" "$success_msg"
