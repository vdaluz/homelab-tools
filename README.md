# homelab-tools

A collection of scripts, utilities, and automation tools used to manage and maintain my homelab infrastructure. These are the small but critical components that keep services running smoothly and handle self-healing across my nodes.

## Repository Purpose

The goal of this repository is to share functional, standalone tools that solve specific infrastructure challenges I've encountered. While most of my infrastructure is managed via Ansible in other repositories, the scripts here are designed to be easily portable or referenced.

## Tools Included

### [Unbound Root Key Recovery](./unbound-root-key-recovery)
- **Problem**: Unbound fails to start if the `root.key` (DNSSEC trust anchor) is corrupted after a power failure.
- **Solution**: A maintenance script for `ExecStartPre` that ensures a fresh, valid anchor is generated before the resolver starts.
- **Tags**: `DNS`, `Unbound`, `Self-healing`, `Systemd`

## Usage

Each tool is contained within its own directory with a dedicated `README.md` explaining installation and configuration.

## License

This project is licensed under the MIT License - see the LICENSE file for details (or feel free to use these scripts as inspiration for your own lab).
