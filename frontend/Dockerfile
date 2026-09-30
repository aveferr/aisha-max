FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
# Скрипты из /docker-entrypoint.d выполняются образом nginx при старте контейнера
COPY docker-entrypoint.d/40-config.sh /docker-entrypoint.d/40-config.sh
RUN sed -i 's/\r$//' /docker-entrypoint.d/40-config.sh && chmod +x /docker-entrypoint.d/40-config.sh

COPY index.html config.js /usr/share/nginx/html/
COPY css /usr/share/nginx/html/css
COPY js /usr/share/nginx/html/js

EXPOSE 80
