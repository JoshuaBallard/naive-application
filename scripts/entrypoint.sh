#!/usr/bin/env sh
# The exclusion list is gitignored and is not in the image. It arrives as a secret and
# is written to disk at boot, because the privacy linter runs on every model response
# and refuses to run without its blocklist.
#
# If EXCLUSIONS_CONTENT is unset, the linter raises and the service does not start.
# That is deliberate: a blind linter reporting success is worse than no linter.
set -eu

if [ -n "${EXCLUSIONS_CONTENT:-}" ]; then
    mkdir -p /repo/security
    printf '%s\n' "$EXCLUSIONS_CONTENT" > /repo/security/exclusions.local.txt
    chmod 600 /repo/security/exclusions.local.txt
fi

exec "$@"
