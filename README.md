# Bluetooth Key Importer (btimport)

[![Python Tests](https://github.com/dalsh/btimport/actions/workflows/test.yml/badge.svg)](https://github.com/dalsh/btimport/actions/workflows/test.yml)

A tool to synchronize Bluetooth link keys from a Windows registry hive to a Linux installation. This is useful for dual-booting systems where you want to use the same Bluetooth devices on both Windows and Linux without re-pairing.

## Requirements

- `python3`
- `chntpw`
- Root privileges (to access `/var/lib/bluetooth`)
- Mounted Windows partition containing the `SYSTEM` hive.

## Installation

You can install the tool using the provided `Makefile`:

```bash
sudo make install
```

This will install the script as `btimport` in `/usr/local/bin/`.

## Usage

1. Mount your Windows partition.

2. Run the tool as root:
   ```bash
   sudo btimport
   ```

   By default, the script looks for the `SYSTEM` hive at:
   `/mnt/windows/Windows/System32/config/SYSTEM`

   You can specify a different path using the `--hive` or `-H` argument:
   ```bash
   sudo btimport --hive /path/to/SYSTEM
   ```

3. Restart the Bluetooth service:
   ```bash
   sudo systemctl restart bluetooth
   ```

## Development

You can run the automated tests using:

```bash
make test
```

## Configuration

If your Windows partition is mounted at a different location, you can use the `--hive` command-line argument.

## How it works

The script uses `chntpw` to read the binary Windows Registry hive without needing Windows APIs. It extracts the Link Keys for all discovered Bluetooth adapters and devices, then updates (or creates) the corresponding configuration files in `/var/lib/bluetooth/`.
