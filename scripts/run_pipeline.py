#!/usr/bin/env python3
"""
End-to-end automation for catalog + STRM generation.

This script orchestrates:
1. Link harvesting (HDFilm & Dizibox)
2. Catalog enrichment
3. STRM generation
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT_DIR = Path(__file__).resolve().parent.parent


def run_step(title: str, command: Sequence[str], env: dict | None = None) -> None:
    print(f"\n=== {title} ===")
    print(" ".join(command))
    subprocess.check_call(command, cwd=ROOT_DIR, env=env or os.environ.copy())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Streamarr pipeline runner.")
    parser.add_argument("--tmdb-key", type=str, default=os.environ.get("TMDB_KEY"), help="TMDB API key")
    parser.add_argument("--resolver-base", type=str, default="http://127.0.0.1:5055", help="Resolver base URL for STRM files")
    parser.add_argument("--hdfilm-limit", type=int, default=None, help="Limit number of HDFilm sitemap files")
    parser.add_argument("--dizibox-max-shows", type=int, default=100, help="Maximum Dizibox shows to process")
    parser.add_argument("--skip-collect", action="store_true", help="Skip link harvesting step")
    parser.add_argument("--skip-strm", action="store_true", help="Skip STRM generation")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    python_exe = sys.executable

    if not args.skip_collect:
        collect_env = os.environ.copy()
        # HDFilm
        cmd = [python_exe, "scripts/collect_links.py", "--site", "hdfilm"]
        if args.hdfilm_limit is not None:
            cmd.extend(["--limit", str(args.hdfilm_limit)])
        run_step("Collecting HDFilm links", cmd, collect_env)

        # Dizibox
        cmd = [python_exe, "scripts/collect_links.py", "--site", "dizibox", "--max-shows", str(args.dizibox_max_shows)]
        run_step("Collecting Dizibox links", cmd, collect_env)
    else:
        print("Skipping link collection.")

    catalog_env = os.environ.copy()
    if args.tmdb_key:
        catalog_env["TMDB_KEY"] = args.tmdb_key
    cmd = [python_exe, "scripts/catalog_builder.py"]
    run_step("Building catalog", cmd, catalog_env)

    if not args.skip_strm:
        cmd = [python_exe, "scripts/strm_generator.py", "--resolver-base", args.resolver_base]
        run_step("Generating STRM files", cmd)
    else:
        print("Skipping STRM generation.")

    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()
