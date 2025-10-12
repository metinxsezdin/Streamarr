#!/usr/bin/env python3
"""
Build Streamarr Jellyfin plugin and optionally run update_manifest.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

ROOT_DIR = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT_DIR / "plugins" / "Streamarr"
DIST_DIR = ROOT_DIR / "dist"
OUTPUT_DIR = DIST_DIR / "Streamarr"
ZIP_PATH = DIST_DIR / "StreamarrPlugin.zip"
MANIFEST_SCRIPT = ROOT_DIR / "scripts" / "update_manifest.py"
DEFAULT_MANIFEST = ROOT_DIR / "docs" / "manifest.json"


def run_command(command: List[str]) -> None:
    subprocess.check_call(command, cwd=ROOT_DIR)


def build_plugin(configuration: str = "Release") -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_command([
        "dotnet",
        "publish",
        str(PLUGIN_DIR / "StreamarrPlugin.csproj"),
        "-c",
        configuration,
        "-o",
        str(OUTPUT_DIR),
    ])


def create_zip() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    shutil.make_archive(str(ZIP_PATH.with_suffix("")), "zip", OUTPUT_DIR)


def run_update_manifest(args: argparse.Namespace) -> None:
    if not MANIFEST_SCRIPT.exists():
        print("update_manifest.py not found; skipping manifest update")
        return

    command = [
        sys.executable,
        str(MANIFEST_SCRIPT),
        "--manifest",
        str(args.manifest or DEFAULT_MANIFEST),
        "--zip",
        str(ZIP_PATH),
        "--version",
        args.version,
        "--target-abi",
        args.target_abi,
        "--source-url",
        args.source_url,
    ]

    if args.guid:
        command.extend(["--guid", args.guid])
    if args.name:
        command.extend(["--name", args.name])
    if args.category:
        command.extend(["--category", args.category])
    if args.owner:
        command.extend(["--owner", args.owner])
    if args.description:
        command.extend(["--description", args.description])
    if args.overview:
        command.extend(["--overview", args.overview])
    if args.image_url:
        command.extend(["--image-url", args.image_url])
    if args.website:
        command.extend(["--website", args.website])
    if args.changelog:
        command.extend(["--changelog", args.changelog])
    if args.runtime:
        command.extend(["--runtime", args.runtime])
    if args.hash_algorithm:
        command.extend(["--hash-algorithm", args.hash_algorithm])

    run_command(command)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Streamarr Jellyfin plugin artifact.")
    parser.add_argument("--configuration", default="Release", help="Build configuration (default: Release)")
    parser.add_argument("--version", help="Plugin version string (passes through to update_manifest)")
    parser.add_argument("--target-abi", help="Target ABI for manifest update")
    parser.add_argument("--source-url", help="Download URL for published zip")
    parser.add_argument("--guid", help="Plugin GUID for manifest")
    parser.add_argument("--name", help="Plugin name for manifest")
    parser.add_argument("--category", help="Plugin category for manifest")
    parser.add_argument("--owner", help="Plugin owner for manifest")
    parser.add_argument("--description", help="Plugin description")
    parser.add_argument("--overview", help="Plugin overview")
    parser.add_argument("--image-url", help="Plugin image URL")
    parser.add_argument("--website", help="Plugin website URL")
    parser.add_argument("--changelog", help="Manifest changelog text")
    parser.add_argument("--runtime", help="Manifest runtime identifier (e.g., net8.0)")
    parser.add_argument("--manifest", help="Manifest path (defaults to docs/manifest.json)")
    parser.add_argument("--hash-algorithm", choices=["md5", "sha256"], help="Hash algorithm for manifest entry")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_plugin(args.configuration)
    create_zip()
    if args.version and args.target_abi and args.source_url:
        run_update_manifest(args)


if __name__ == "__main__":
    main()
