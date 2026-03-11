#!/usr/bin/env python3

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

__version__ = "1.0.0"

import os
import subprocess
import re
import sys

import argparse

# ANSI color codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

DEFAULT_SYSTEM_HIVE = "/mnt/windows/Windows/System32/config/SYSTEM"
LINUX_BLUETOOTH_PATH = "/var/lib/bluetooth"

def run_chntpw_cmd(commands, hive_path):
    full_cmd = "\n".join(commands) + "\nq\n"
    process = subprocess.Popen(
        ["chntpw", "-e", hive_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = process.communicate(input=full_cmd)
    return stdout

def get_adapter_macs(hive_path):
    output = run_chntpw_cmd(["cd \\ControlSet001\\Services\\BTHPORT\\Parameters\\Keys", "ls"], hive_path)
    # Look for patterns like <001a7dda7113>
    macs = re.findall(r"<([0-9a-fA-F]{12})>", output)
    return [mac.lower() for mac in macs]

def get_keys_for_adapter(adapter_mac, hive_path):
    output = run_chntpw_cmd([
        f"cd \\ControlSet001\\Services\\BTHPORT\\Parameters\\Keys\\{adapter_mac}",
        "ls"
    ], hive_path)
    
    # We are looking for values that are REG_BINARY and have 12 hex chars as name (device MAC)
    # Example line: 16  3 REG_BINARY         <2c7600ddf69c>
    matches = re.findall(r"16\s+3\s+REG_BINARY\s+<([0-9a-fA-F]{12})>", output)
    
    keys = {}
    for device_mac in matches:
        hex_output = run_chntpw_cmd([
            f"cd \\ControlSet001\\Services\\BTHPORT\\Parameters\\Keys\\{adapter_mac}",
            f"hex {device_mac}"
        ], hive_path)
        # Example hex output: :00000  33 71 43 8D DC E7 0E BF DC 48 20 DA 60 31 C4 B9 3qC......H .`1..
        hex_match = re.search(r":00000\s+((?:[0-9a-fA-F]{2}\s*){16})", hex_output)
        if hex_match:
            key_hex = hex_match.group(1).replace(" ", "").upper()
            keys[device_mac.lower()] = key_hex
            
    return keys

def format_mac(mac):
    """001a7dda7113 -> 00:1A:7D:DA:71:13"""
    return ":".join(mac[i:i+2].upper() for i in range(0, 12, 2))

def update_linux_config(adapter_mac, device_mac, key):
    adapter_dir_name = format_mac(adapter_mac)
    device_dir_name = format_mac(device_mac)
    
    adapter_path = os.path.join(LINUX_BLUETOOTH_PATH, adapter_dir_name)
    device_path = os.path.join(adapter_path, device_dir_name)
    info_path = os.path.join(device_path, "info")
    
    # Create directories if they don't exist
    if not os.path.exists(device_path):
        print(f"[*] Creating directory for {device_dir_name} on adapter {adapter_dir_name}")
        try:
            os.makedirs(device_path, mode=0o700, exist_ok=True)
        except Exception as e:
            print(f"{RED}[!] Error creating directory {device_path}: {e}{RESET}")
            return False, False
    
    # Create info file if it doesn't exist
    if not os.path.exists(info_path):
        print(f"[*] Creating new info file for {device_dir_name}")
        try:
            with open(info_path, "w") as f:
                f.write("[General]\nTrusted=true\n\n[LinkKey]\n")
        except Exception as e:
            print(f"{RED}[!] Error creating {info_path}: {e}{RESET}")
            return False, False
    
    try:
        with open(info_path, "r") as f:
            content = f.read()
        
        # Look for [LinkKey] section and Key=...
        if "[LinkKey]" not in content:
            # If [LinkKey] is missing, append it
            new_content = content.strip() + "\n\n[LinkKey]\n"
        else:
            new_content = content
            
        if "Key=" in new_content:
            # Update existing key
            new_content = re.sub(r"^Key=[0-9A-F]+", f"Key={key}", new_content, flags=re.MULTILINE)
        else:
            # Append Key to [LinkKey] section
            new_content = new_content.replace("[LinkKey]", f"[LinkKey]\nKey={key}")
        
        if new_content == content:
            print(f"[*] Key for {device_dir_name} is already up to date.")
            return True, False
            
        with open(info_path, "w") as f:
            f.write(new_content)
        print(f"{GREEN}[+] Updated key for {device_dir_name}{RESET}")
        return True, True
    except Exception as e:
        print(f"{RED}[!] Error updating {info_path}: {e}{RESET}")
        return False, False

def main():
    parser = argparse.ArgumentParser(description="Synchronize Bluetooth link keys from Windows to Linux.")
    parser.add_argument(
        "--hive", "-H", 
        default=DEFAULT_SYSTEM_HIVE,
        help=f"Path to the Windows SYSTEM registry hive (default: {DEFAULT_SYSTEM_HIVE})"
    )
    parser.add_argument(
        "--version", "-V",
        action="store_true",
        help="Print version information and license snippet"
    )
    args = parser.parse_args()

    if args.version:
        print(f"btimport version {__version__}")
        print("Copyright (C) 2026")
        print("\nThis program comes with ABSOLUTELY NO WARRANTY;")
        print("This is free software, and you are welcome to redistribute it")
        print("under certain conditions; see the GNU General Public License v3 for details.")
        sys.exit(0)

    if os.getuid() != 0:
        print(f"{RED}Error: This script must be run as root to access /var/lib/bluetooth{RESET}\n")
        parser.print_help()
        sys.exit(1)
        
    hive_path = args.hive
    if not os.path.exists(hive_path):
        print(f"{RED}Error: Windows SYSTEM hive not found at {hive_path}{RESET}")
        sys.exit(1)
        
    print(f"[*] Reading Windows Registry from {hive_path}...")
    adapters = get_adapter_macs(hive_path)
    if not adapters:
        print(f"{YELLOW}[-] No Bluetooth adapters found in Windows Registry.{RESET}")
        return

    total_updated = 0
    for adapter in adapters:
        print(f"[*] Processing Adapter: {format_mac(adapter)}")
        keys = get_keys_for_adapter(adapter, hive_path)
        for device_mac, key in keys.items():
            print(f"[*] Found Device: {format_mac(device_mac)} with Key: {key}")
            success, updated = update_linux_config(adapter, device_mac, key)
            if updated:
                total_updated += 1
            
    if total_updated > 0:
        print(f"\n{GREEN}[+] Success: {total_updated} keys were updated.{RESET}")
        print(f"{YELLOW}[!] IMPORTANT: You should probably restart the Bluetooth service for changes to take effect.{RESET}")
    else:
        print(f"\n{GREEN}[*] No changes were made. Everything is already up to date.{RESET}")

if __name__ == "__main__":
    main()
