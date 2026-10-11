#!/bin/sh
# Start as root only long enough to make the mounted volume writable by the app user,
# then run the server as that user. Fly mounts volumes owned by root; the app itself
# never runs as root (Dockerfile). Without a volume (local docker run) this is a no-op.
set -eu

if [ "$(id -u)" = "0" ]; then
    chown wiggle:nogroup /data 2>/dev/null || true
    exec runuser -u wiggle -- "$@"
fi
exec "$@"
