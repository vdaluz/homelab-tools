#!/bin/bash
# Apple Music Library Export
# Exports the local Music.app library (tracks + playlists) to a Library.xml
# file inside ~/Music, so an existing file-level backup (Time Machine, etc.)
# picks it up on its normal schedule. No third-party tools required.

set -uo pipefail

EXPORT_DIR="${MUSIC_LIBRARY_EXPORT_DIR:-$HOME/Music/Library Export}"
EXPORT_PATH="${MUSIC_LIBRARY_EXPORT_PATH:-$EXPORT_DIR/Library.xml}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

main() {
    mkdir -p "$EXPORT_DIR"

    log "Exporting Music library to ${EXPORT_PATH}"

    osascript <<OSA
tell application "Music"
    export source "Library" as XML to POSIX file "${EXPORT_PATH}"
end tell
OSA

    if [ -s "${EXPORT_PATH}" ]; then
        log "Export complete: $(du -h "${EXPORT_PATH}" | cut -f1)"
    else
        log "Export FAILED: ${EXPORT_PATH} is missing or empty"
        exit 1
    fi
}

main "$@"
