# Apple Music Library Export

A scheduled export of your local Music.app library (tracks + playlists) to a
`Library.xml` file, so an existing file-level backup already picks it up -
no third-party export tool required.

## Overview

macOS Music.app can export your full library (tracks and playlists in one
file) via its own built-in AppleScript `export` command. This tool wraps
that command in a small script and a `launchd` LaunchAgent so it runs on a
daily schedule, writing into `~/Music/Library Export/Library.xml` - a path
already covered by most whole-home-directory backup setups (Time Machine,
etc.), so no new backup transport is needed.

Each run overwrites the same file rather than writing timestamped copies;
your existing backup's own snapshot history provides the version retention.

## Installation

1. Copy `export-music-library.sh` and `local.music-library-export.plist`
   to a permanent location, e.g. `~/Scripts/apple-music-library-export/`.
2. Edit `local.music-library-export.plist` and replace
   `REPLACE_WITH_ABSOLUTE_SCRIPT_PATH` with the absolute path to
   `export-music-library.sh`.
3. Copy the plist to `~/Library/LaunchAgents/` and load it:
   ```
   cp local.music-library-export.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/local.music-library-export.plist
   ```
4. To run it immediately instead of waiting for the next scheduled time:
   ```
   launchctl kickstart -k gui/$(id -u)/local.music-library-export
   ```

The default schedule is 04:00 local time; edit the `StartCalendarInterval`
block in the plist to change it.

## Script Features

- **No third-party tools** - uses Music.app's own native AppleScript
  `export` command, which produces the same `Library.xml` format as the
  classic iTunes "Export Library" menu item (tracks + playlists in one
  file).
- **Idempotent output path** - always writes to the same file, relying on
  your existing backup for history rather than accumulating copies.
- **Logging** - run output (including a failure message if the export
  produced no file) goes to the path set in the plist's `StandardOutPath`.
