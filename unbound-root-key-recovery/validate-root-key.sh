#!/bin/bash
# Unbound Root Key Maintenance Script
# Ensures the `root.key` trust anchor is removed and regenerated before Unbound starts.

set -uo pipefail

ROOT_KEY_PATH="${UNBOUND_ROOT_KEY_PATH:-/var/lib/unbound/root.key}"

log() {
    local priority="${1:-daemon.notice}"
    shift
    logger -t "unbound-root-key-validator" -p "${priority}" "$@" 2>/dev/null || true
}

main() {
    log daemon.info "Ensuring root.key is valid before Unbound starts"

    if [ -f "${ROOT_KEY_PATH}" ]; then
        log daemon.notice "Removing existing root.key at ${ROOT_KEY_PATH} to force regeneration"
        rm -f "${ROOT_KEY_PATH}"
    else
        log daemon.debug "No root.key file found at ${ROOT_KEY_PATH}"
    fi

    # Regenerate the key immediately to ensure it exists for Unbound
    if [ -x /usr/libexec/unbound-helper ]; then
        log daemon.notice "Regenerating root.key using unbound-helper"
        /usr/libexec/unbound-helper root_trust_anchor_update || true
    elif command -v unbound-anchor >/dev/null 2>&1; then
        log daemon.notice "Regenerating root.key using unbound-anchor"
        unbound-anchor -a "${ROOT_KEY_PATH}" || true
        if [ -d "$(dirname "${ROOT_KEY_PATH}")" ] && command -v getent >/dev/null 2>&1; then
            chown unbound:unbound "${ROOT_KEY_PATH}" >/dev/null 2>&1 || true
        fi
    else
        log daemon.warning "No tool found to regenerate root.key! Unbound may fail to start."
    fi

    exit 0
}

main "$@"
