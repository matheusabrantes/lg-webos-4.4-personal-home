#!/usr/bin/env python3
"""Package the silent startup bridge; never contacts or installs to a TV."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import zlib

HERE = Path(__file__).resolve().parent
APP_ID = "com.personalhome.startup"
MIN_FREE = 20 * 1024 ** 3
PEAK_BYTES = 8 * 1024 ** 2
MARGIN_BYTES = 64 * 1024 ** 2


def black_icon():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 80, 80, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\x00" + b"\x00" * 240) * 80))
            + chunk(b"IEND", b""))


def payloads(nonce):
    if not re.fullmatch(r"[a-f0-9]{32}", nonce):
        raise ValueError("nonce must be 32 lowercase hexadecimal characters")
    bridge = (HERE / "bridge.js").read_text()
    if bridge.count("__NONCE__") != 1:
        raise ValueError("bridge nonce placeholder must appear exactly once")
    service = (HERE / "service/service.js").read_text()
    if service.count("__NONCE__") != 1:
        raise ValueError("service nonce placeholder must appear exactly once")
    return {
        "appinfo.json": (HERE / "appinfo.json").read_bytes(),
        "index.html": (HERE / "index.html").read_bytes(),
        "bridge.js": bridge.replace("__NONCE__", nonce).encode(),
        "icon.png": black_icon(),
        "service/package.json": (HERE / "service/package.json").read_bytes(),
        "service/services.json": (HERE / "service/services.json").read_bytes(),
        "service/service.js": service.replace("__NONCE__", nonce).encode(),
        "service/readiness.js": (HERE / "service/readiness.js").read_bytes(),
    }


def check_space(output):
    target = output.parent
    while not target.exists():
        target = target.parent
    volumes = {target.resolve()}
    mac_volume = Path("/System/Volumes/Data")
    if mac_volume.exists():
        volumes.add(mac_volume)
    for volume in volumes:
        available = shutil.disk_usage(volume).free
        required = MIN_FREE + PEAK_BYTES + MARGIN_BYTES
        if available < required:
            raise RuntimeError(
                f"Storage reserve: {available} bytes available on {volume}; "
                f"need {required} (20 GiB reserve + 8 MiB peak + 64 MiB margin)")


def build(nonce, output):
    files = payloads(nonce)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("output directory must be new")
    packager = shutil.which("ares-package")
    if not packager:
        raise RuntimeError("installed ares-package is required")
    check_space(output)
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="personalhome-startup-", dir=output.parent) as temporary:
        stage = Path(temporary)
        (stage / "app").mkdir()
        (stage / "service").mkdir()
        for name, data in files.items():
            target = stage / name if name.startswith("service/") else stage / "app" / name
            target.write_bytes(data)
        result = subprocess.run([packager, "--outdir", str(output), str(stage / "app"), str(stage / "service")],
                                capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
    packages = list(output.glob("*.ipk"))
    if len(packages) != 1:
        raise RuntimeError("ares-package did not produce exactly one package")
    package = packages[0]
    return {"appId": APP_ID, "serviceId": APP_ID + ".service", "nonce": nonce, "ipk": str(package),
            "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            "watchdogMs": 75000, "installed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.nonce, args.output), indent=2))
