"""
Levoit Sprout — SPIFFS asset builder
PlatformIO pre-build script.

Reads files from the `data/` folder next to the device yaml,
builds a SPIFFS image using ESP-IDF's bundled spiffsgen.py,
and registers it as an extra binary to flash at the `assets`
partition offset (0x290000).

Usage:
  - Place audio files in devices/levoit-sprout/data/
  - ESPHome build picks this up automatically via extra_scripts

No extra Python dependencies — spiffsgen.py ships with ESP-IDF.
"""

Import("env")  # noqa: F821 — PlatformIO injects this

import os
import sys
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure fatfs-ng is installed and fatfs (old conflicting package) is not.
# The platform builder (main.py) imports fatfs after our pre-script runs,
# so we can fix the environment here before it tries.
# ---------------------------------------------------------------------------
def _ensure_fatfs_ng():
    try:
        from fatfs import create_extended_partition  # noqa: F401
        return  # already correct
    except ImportError:
        pass

    # Remove old conflicting fatfs if present
    try:
        import fatfs  # noqa: F401
        subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "fatfs", "-y"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[assets] Removed conflicting 'fatfs' package")
    except ImportError:
        pass

    # Install fatfs-ng
    print("[assets] Installing fatfs-ng ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fatfs-ng>=0.1.14"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("[assets] fatfs-ng installed")

_ensure_fatfs_ng()

# ---------------------------------------------------------------------------
# Config — must match the active partitions csv (partitions_4mb.csv)
# ---------------------------------------------------------------------------
ASSETS_PARTITION_OFFSET = 0x290000
ASSETS_PARTITION_SIZE   = 0x170000   # ~1.44 MB

# Derive device yaml directory from PlatformIO PROJECT_DIR.
# PROJECT_DIR = <config_dir>/.esphome/build/<device>/  (3 levels deep)
SCRIPT_DIR = Path(env.subst("$PROJECT_DIR")).parents[2]
DATA_DIR   = SCRIPT_DIR / "data"
IMAGE_OUT  = Path(env.subst("$BUILD_DIR")) / "assets_spiffs.bin"

# spiffsgen.py ships with ESP-IDF — no pip install needed
SPIFFSGEN  = (Path(env.subst("$PROJECT_PACKAGES_DIR"))
              / "framework-espidf" / "components" / "spiffs" / "spiffsgen.py")

# ---------------------------------------------------------------------------

def _select_files():
    """
    Return (included, skipped) lists of (Path, size) tuples that fit.
    Only MP3 files are included — OGG is not supported (stb_vorbis requires
    loading the entire file plus ~200 KB of codebook state into heap, which
    is not feasible on this ESP32 without PSRAM).
    """
    if not DATA_DIR.exists():
        return [], []

    raw_files = sorted(
        f for f in DATA_DIR.iterdir()
        if f.is_file() and f.suffix.lower() == ".mp3"
    )
    ogg_files = [f for f in DATA_DIR.iterdir() if f.is_file() and f.suffix.lower() == ".ogg"]
    for f in ogg_files:
        print(f"[assets] Skipping OGG (not supported): {f.name}  — convert to MP3 first")

    all_files = raw_files
    # SPIFFS overhead per file: roughly one page (256 bytes) for metadata
    PAGE_SIZE = 256
    usable = ASSETS_PARTITION_SIZE - PAGE_SIZE  # conservative estimate
    included, skipped, used = [], [], 0
    for f in all_files:
        size = f.stat().st_size
        cost = size + PAGE_SIZE
        if used + cost <= usable:
            included.append((f, size))
            used += cost
        else:
            skipped.append((f, size))
    return included, skipped


def build_spiffs_image():
    if not DATA_DIR.exists():
        print(f"[assets] data/ not found at {DATA_DIR} — skipping SPIFFS build")
        return False

    included, skipped = _select_files()
    if not included:
        print("[assets] No audio files to include — skipping SPIFFS build")
        return False

    if not SPIFFSGEN.exists():
        print(f"[assets] WARNING: spiffsgen.py not found at {SPIFFSGEN}")
        return False

    print(f"[assets] Partition: {ASSETS_PARTITION_SIZE // 1024} KB")
    print(f"[assets] Including ({len(included)} files):")
    for f, size in included:
        print(f"  + {f.name:30s}  {size:>8,} bytes")
    if skipped:
        print(f"[assets] Skipped (no space):")
        for f, size in skipped:
            print(f"  - {f.name:30s}  {size:>8,} bytes")

    # Build a staging directory with only the selected files so spiffsgen
    # doesn't accidentally pick up extras.
    import tempfile, shutil
    with tempfile.TemporaryDirectory() as staging:
        for f, _ in included:
            shutil.copy2(f, os.path.join(staging, f.name))

        IMAGE_OUT.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [sys.executable, str(SPIFFSGEN),
             str(ASSETS_PARTITION_SIZE), staging, str(IMAGE_OUT)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"[assets] spiffsgen.py failed:\n{result.stderr}")
            return False

    size_kb = IMAGE_OUT.stat().st_size // 1024
    print(f"[assets] Image written: {IMAGE_OUT.name}  ({size_kb} KB)")
    return True


def add_flash_target(source, target, env):
    """Append the SPIFFS image to the esptool upload command."""
    if not IMAGE_OUT.exists():
        return
    env.Append(UPLOADERFLAGS=[
        hex(ASSETS_PARTITION_OFFSET),
        str(IMAGE_OUT),
    ])
    print(f"[assets] Added to upload: {hex(ASSETS_PARTITION_OFFSET)} {IMAGE_OUT.name}")


# ---------------------------------------------------------------------------
# Add esp_driver_i2s include path so levoit_audio.cpp can find driver/i2s_std.h
# ESPHome external components are compiled as part of the main app, not as
# separate IDF components, so CMakeLists.txt REQUIRES don't add include paths.
# ---------------------------------------------------------------------------
def _patch_src_cmake_requires(components):
    """
    Add REQUIRES <components> to the main app's src/CMakeLists.txt so ESP-IDF CMake
    compiles and links them.  Must run before cmake configuration; pre-scripts do.
    ESPHome regenerates the file only on YAML changes — re-patching is idempotent.
    """
    import re
    src_cmake = Path(env.subst("$PROJECT_DIR")) / "src" / "CMakeLists.txt"
    if not src_cmake.exists():
        print(f"[assets] WARNING: {src_cmake} not found — cannot inject REQUIRES")
        return

    content = src_cmake.read_text(encoding="utf-8")
    missing = [c for c in components if c not in content]
    if not missing:
        print(f"[assets] src/CMakeLists.txt already has: {' '.join(components)}")
        return

    missing_str = " ".join(missing)
    if re.search(r'\bREQUIRES\b', content):
        content = re.sub(r'\bREQUIRES\b', f'REQUIRES {missing_str}', content, count=1)
    elif 'idf_component_register(' in content:
        content = content.replace(
            'idf_component_register(',
            f'idf_component_register(REQUIRES {missing_str} ',
            1,
        )
    else:
        print("[assets] WARNING: idf_component_register not found in src/CMakeLists.txt")
        return

    src_cmake.write_text(content, encoding="utf-8")
    print(f"[assets] Patched src/CMakeLists.txt: added REQUIRES {missing_str}")


def _add_idf_includes():
    packages_dir = env.subst("$PROJECT_PACKAGES_DIR")
    idf_base = os.path.join(packages_dir, "framework-espidf", "components")

    # Include paths for headers not in the default search path.
    # vendor/ is NOT copied by ESPHome to the build tree (it only copies top-level
    # component files), so point the compiler at the original source dir.
    vendor_dir = str(SCRIPT_DIR.parent.parent / "components" / "levoit_audio" / "vendor")
    extra_includes = [
        vendor_dir,
        os.path.join(idf_base, "esp_driver_i2s", "include"),
        os.path.join(idf_base, "spiffs", "include"),
    ]
    for inc in extra_includes:
        if os.path.isdir(inc):
            env.Append(CPPPATH=[inc])
            print(f"[assets] Added include: {inc}")
        else:
            print(f"[assets] WARNING: include not found: {inc}")

    # Patch src/CMakeLists.txt so the main app's idf_component_register declares REQUIRES
    # for our needed components.  This runs before cmake configuration (pre-scripts run
    # first in PlatformIO), so cmake sees the patched file and compiles these components.
    # ESPHome only regenerates the file when the YAML changes; the patch is re-applied
    # each build, so it's idempotent.
    _patch_src_cmake_requires(["esp_driver_i2s", "spiffs"])

    # Pre-action: inject LIBPATH + LIBS just before firmware.elf links.
    # By this point the CMake REQUIRES above has caused the component .a files to be
    # built.  Fires only for firmware.elf — not bootloader.elf (different target path).
    def _inject_app_libs(source, target, env):
        bd = env.subst("$BUILD_DIR")
        for lib in ("esp_driver_i2s", "spiffs"):
            lib_dir = os.path.join(bd, "esp-idf", lib)
            if os.path.isdir(lib_dir):
                env.Append(LIBPATH=[lib_dir])
                env.Prepend(LIBS=[lib])
                print(f"[assets] Linked: {lib}")
            else:
                print(f"[assets] WARNING: lib dir missing at link time: {lib_dir}")

    env.AddPreAction("$BUILD_DIR/${PROGNAME}.elf", _inject_app_libs)

_add_idf_includes()

# Build image at the start of the compile phase
if build_spiffs_image():
    # Hook: inject into the upload command after the firmware is linked
    env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", add_flash_target)
