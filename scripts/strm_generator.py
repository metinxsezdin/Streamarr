#!/usr/bin/env python3
"""
Generate .strm files from catalog entries.
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate STRM files from catalog JSON.")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=ROOT_DIR / "data/catalog.json",
        help="Path to catalog JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "output/strm",
        help="Directory to place STRM files",
    )
    parser.add_argument(
        "--resolver-base",
        type=str,
        default="http://127.0.0.1:5055",
        help="Base URL for resolver API (used in STRM)",
    )
    return parser.parse_args()


def sanitize_filename(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.strip()
    return "".join(c if c.isalnum() or c in " -._" else "_" for c in ascii_name)


def build_strm_content(resolver_base: str, entry_id: str) -> str:
    encoded_id = quote(entry_id, safe="")
    return f"{resolver_base.rstrip('/')}/play/{encoded_id}"


def main() -> None:
    args = parse_args()
    catalog_data = json.loads(args.catalog.read_text(encoding="utf-8"))
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for entry in catalog_data:
        title = entry.get("title") or entry.get("original_title") or "Untitled"
        subtitle = entry.get("subtitle") or ""
        entry_id = entry["id"]
        entry_type = entry.get("type", "movie")

        if entry_type == "episode" and subtitle:
            filename = sanitize_filename(f"{title} - {subtitle}.strm")
            series_dir = output_dir / sanitize_filename(title)
            series_dir.mkdir(parents=True, exist_ok=True)
            target_path = series_dir / filename
        else:
            filename = sanitize_filename(f"{title}.strm")
            target_path = output_dir / filename

        content = build_strm_content(args.resolver_base, entry_id)
        target_path.write_text(content + "\n", encoding="utf-8")
        count += 1

    print(f"[strm] generated {count} files in {output_dir}")


if __name__ == "__main__":
    main()
