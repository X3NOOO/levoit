#!/usr/bin/env python3
"""
Flash Levoit Sprout via USB.

Modes:
  full   — flash partition table + firmware + SPIFFS assets (required first time)
  assets — flash only the SPIFFS assets partition (subsequent updates)

Usage:
  python flash_assets.py [full|assets] [COMx]
"""

import sys
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
BUILD_DIR  = SCRIPT_DIR / ".esphome/build/levoit-sprout/.pioenvs/levoit-sprout"

FACTORY_IMAGE   = BUILD_DIR / "firmware.factory.bin"   # merged: bootloader+pt+app
PARTITIONS_BIN  = BUILD_DIR / "partitions.bin"
FIRMWARE_BIN    = BUILD_DIR / "firmware.bin"
SPIFFS_IMAGE    = BUILD_DIR / "assets_spiffs.bin"

FACTORY_OFFSET   = "0x0"
PARTITIONS_OFFSET = "0x8000"
FIRMWARE_OFFSET  = "0x10000"
SPIFFS_OFFSET    = "0x290000"

BAUD = "460800"


def pick_port():
    try:
        from serial.tools.list_ports import comports
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyserial", "-q"])
        from serial.tools.list_ports import comports

    ports = sorted(comports(), key=lambda p: p.device)
    if not ports:
        print("No serial ports found. Connect the device and try again.")
        sys.exit(1)
    if len(ports) == 1:
        print(f"Using: {ports[0].device}  ({ports[0].description})")
        return ports[0].device

    print("Available serial ports:")
    for i, p in enumerate(ports):
        print(f"  [{i+1}] {p.device}  —  {p.description}")
    while True:
        choice = input(f"Select port [1-{len(ports)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(ports):
            return ports[int(choice) - 1].device
        print("Invalid choice.")


def flash(port, pairs):
    """pairs = [(offset, path), ...]"""
    args = []
    for offset, path in pairs:
        args += [offset, str(path)]
    cmd = [
        sys.executable, "-m", "esptool",
        "--chip", "esp32",
        "--port", port,
        "--baud", BAUD,
        "--before", "default_reset",
        "--after", "hard_reset",
        "write_flash", "--flash_mode", "dio",
        *args,
    ]
    print(f"\nRunning: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def check_exists(*paths):
    missing = [p for p in paths if not p.exists()]
    if missing:
        for p in missing:
            print(f"ERROR: not found: {p}")
        print("Run 'esphome compile' first.")
        sys.exit(1)


def main():
    args = sys.argv[1:]

    # parse mode
    mode = "full"
    if args and args[0] in ("full", "assets"):
        mode = args.pop(0)
    elif not args:
        print("First time flashing this device? You must do a FULL flash to update")
        print("the partition table. Choose:\n")
        print("  [1] full   — partition table + firmware + SPIFFS  (required first time)")
        print("  [2] assets — SPIFFS only  (subsequent audio updates)")
        choice = input("\nSelect [1/2]: ").strip()
        mode = "assets" if choice == "2" else "full"

    port = args[0] if args else pick_port()

    if mode == "full":
        if FACTORY_IMAGE.exists():
            check_exists(FACTORY_IMAGE, SPIFFS_IMAGE)
            size_fw = FACTORY_IMAGE.stat().st_size
            size_sp = SPIFFS_IMAGE.stat().st_size
            print(f"\nFull flash:")
            print(f"  {FACTORY_OFFSET:>12}  firmware.factory.bin  ({size_fw:,} bytes)")
            print(f"  {SPIFFS_OFFSET:>12}  assets_spiffs.bin     ({size_sp:,} bytes)")
            flash(port, [(FACTORY_OFFSET, FACTORY_IMAGE), (SPIFFS_OFFSET, SPIFFS_IMAGE)])
        else:
            # fallback: flash individual parts
            check_exists(PARTITIONS_BIN, FIRMWARE_BIN, SPIFFS_IMAGE)
            print(f"\nFull flash (individual parts):")
            print(f"  {PARTITIONS_OFFSET:>12}  partitions.bin")
            print(f"  {FIRMWARE_OFFSET:>12}  firmware.bin")
            print(f"  {SPIFFS_OFFSET:>12}  assets_spiffs.bin")
            flash(port, [
                (PARTITIONS_OFFSET, PARTITIONS_BIN),
                (FIRMWARE_OFFSET,   FIRMWARE_BIN),
                (SPIFFS_OFFSET,     SPIFFS_IMAGE),
            ])
    else:
        check_exists(SPIFFS_IMAGE)
        size = SPIFFS_IMAGE.stat().st_size
        print(f"\nAssets-only flash:")
        print(f"  {SPIFFS_OFFSET:>12}  assets_spiffs.bin  ({size:,} bytes)")
        flash(port, [(SPIFFS_OFFSET, SPIFFS_IMAGE)])


if __name__ == "__main__":
    main()
