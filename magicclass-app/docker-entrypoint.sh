#!/bin/sh
# magicclass-app entrypoint.
#
# The runtime data directory (/app/data) is a named volume. Docker creates a
# fresh named volume owned by root, and volumes from older deployments may also
# be root-owned, while the app runs as the unprivileged `nextjs` user. Classrooms,
# generation jobs, material bytes and usage logs all live under /app/data, so the
# app cannot write them until the directory is owned by nextjs.
#
# The container therefore starts as root, fixes the ownership here, and then
# drops to `nextjs` with su-exec before running Node. This keeps a non-root app
# user (no chmod 777, no long-running root). The chown is idempotent and only
# changes ownership: it never deletes or overwrites existing volume data, so
# rebuilding the container preserves data and initialisation does not clobber it.
set -eu

DATA_DIR="${MAGICCLASS_DATA_DIR:-/app/data}"

mkdir -p "$DATA_DIR"
chown -R nextjs:nodejs "$DATA_DIR"

exec su-exec nextjs:nodejs node server.js
