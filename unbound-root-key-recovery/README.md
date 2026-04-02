# Unbound Root Key Recovery

A self-healing script for Unbound DNS resolvers that prevents startup failures caused by corrupted DNSSEC trust anchors after unclean shutdowns.

## Overview

After power failures or hard resets, Unbound's `root.key` file can become corrupted with duplicate or conflicting DNSSEC trust anchor entries. Unbound's validator module detects this corruption and refuses to start.

This tool provides a maintenance script meant to be run as a systemd `ExecStartPre` hook. It ensures a fresh trust anchor is regenerated on every service start.

## Installation

1. Copy `validate-root-key.sh` to `/usr/local/bin/` and make it executable.
2. Create a systemd override for Unbound:
   ```ini
   [Service]
   ExecStartPre=/usr/local/bin/validate-root-key.sh
   ```

## Script Features

- **Automated Cleanup**: Removes existing `root.key` before Unbound starts.
- **Regeneration**: Uses `unbound-anchor` or `unbound-helper` to immediately fetch a fresh anchor.
- **Logging**: Sends events to the system journal with the tag `unbound-root-key-validator`.
