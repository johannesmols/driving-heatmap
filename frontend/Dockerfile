FROM nginx:alpine

# Install bun for building frontend at container startup
RUN apk add --no-cache bash curl unzip \
    && curl -fsSL https://bun.sh/install | bash \
    && ln -s /root/.bun/bin/bun /usr/local/bin/bun

# Writable workspace for build step (source is mounted read-only at /app/src)
RUN mkdir -p /app

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
