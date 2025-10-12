#!/usr/bin/env python3
"""
Utility script to update a Jellyfin plugin manifest entry.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List


def compute_hash(zip_path: Path, algorithm: str) -> str:
    algo = algorithm.lower()
    if algo not in {"md5", "sha256"}:
        raise ValueError("Unsupported hash algorithm. Use 'md5' or 'sha256'.")

    hasher = hashlib.new(algo)
    with zip_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    return f"{algo}:{digest}" if algo == "sha256" else digest


def load_manifest(manifest_path: Path) -> List[Dict[str, Any]]:
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return []


def save_manifest(manifest_path: Path, data: List[Dict[str, Any]]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_entry(manifest: List[Dict[str, Any]], args: argparse.Namespace) -> Dict[str, Any]:
    entry = None
    if args.guid:
        entry = next((item for item in manifest if item.get("guid") == args.guid), None)
    if entry is None and args.name:
        entry = next((item for item in manifest if item.get("name") == args.name), None)

    if entry is None:
        if not (args.guid and args.name):
            raise ValueError("Manifest entry not found. Provide both --guid and --name to create a new entry.")
        entry = {
            "guid": args.guid,
            "name": args.name,
            "category": args.category or "General",
            "description": args.description or "",
            "overview": args.overview or "",
            "owner": args.owner or "",
            "imageUrl": args.image_url or "",
            "versions": [],
        }
        manifest.append(entry)

    if args.category:
        entry["category"] = args.category
    if args.description:
        entry["description"] = args.description
    if args.overview:
        entry["overview"] = args.overview
    if args.owner:
        entry["owner"] = args.owner
    if args.image_url:
        entry["imageUrl"] = args.image_url
    if args.website:
        entry["website"] = args.website

    return entry


def update_versions(entry: Dict[str, Any], args: argparse.Namespace, checksum: str) -> None:
    versions: List[Dict[str, Any]] = entry.setdefault("versions", [])
    versions = [v for v in versions if v.get("version") != args.version]

    timestamp = args.timestamp or dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    version_entry = {
        "version": args.version,
        "targetAbi": args.target_abi,
        "sourceUrl": args.source_url,
        "checksum": checksum,
        "timestamp": timestamp,
    }
    if args.changelog:
        version_entry["changelog"] = args.changelog
    if args.runtime:
        version_entry["runtime"] = args.runtime

    versions.insert(0, version_entry)
    entry["versions"] = versions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Jellyfin plugin manifest.")
    parser.add_argument("--manifest", type=Path, required=True, help="Path to manifest.json")
    parser.add_argument("--zip", type=Path, required=True, help="Path to plugin zip file")
    parser.add_argument("--version", required=True, help="Version string (e.g., 0.1.1)")
    parser.add_argument("--target-abi", required=True, help="Target ABI (e.g., 10.9.0.0)")
    parser.add_argument("--source-url", required=True, help="Download URL for the zip")
    parser.add_argument("--hash-algorithm", choices=["md5", "sha256"], default="md5")
    parser.add_argument("--guid", help="Plugin GUID")
    parser.add_argument("--name", help="Plugin name")
    parser.add_argument("--category", help="Plugin category")
    parser.add_argument("--description", help="Plugin description")
    parser.add_argument("--overview", help="Plugin overview")
    parser.add_argument("--owner", help="Plugin owner")
    parser.add_argument("--image-url", help="Plugin image URL")
    parser.add_argument("--website", help="Plugin website URL")
    parser.add_argument("--changelog", help="Changelog text")
    parser.add_argument("--runtime", help="Runtime identifier (e.g., net8.0)")
    parser.add_argument("--timestamp", help="ISO timestamp (defaults to UTC now)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.zip.exists():
        raise FileNotFoundError(f"ZIP file not found: {args.zip}")

    checksum = compute_hash(args.zip, args.hash_algorithm)
    manifest_data = load_manifest(args.manifest)
    entry = ensure_entry(manifest_data, args)
    update_versions(entry, args, checksum)
    save_manifest(args.manifest, manifest_data)

    print(f"Updated manifest at {args.manifest}")
    print(f" -> version {args.version}")
    print(f" -> checksum {checksum}")


if __name__ == "__main__":
    main()
