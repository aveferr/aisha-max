#!/bin/sh
# Формирует config.js из переменных окружения контейнера.
set -eu

# В значения пропускаем только безопасные символы: они попадают в JavaScript.
sanitize() { printf '%s' "$1" | tr -cd 'A-Za-z0-9_./-'; }

BOT_USERNAME=$(sanitize "${MAX_BOT_USERNAME:-}")
TIME_ZONE=$(sanitize "${TIMEZONE:-Europe/Moscow}")

cat > /usr/share/nginx/html/config.js <<EOF
window.APP_CONFIG = {
  apiBase: "/api/v1",
  botUsername: "${BOT_USERNAME}",
  timezone: "${TIME_ZONE}"
};
EOF
