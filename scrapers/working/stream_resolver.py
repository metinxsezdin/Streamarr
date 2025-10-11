#!/usr/bin/env python3
"""
On-demand stream resolver for supported Turkish streaming sites.

This module wraps the existing scraper classes and provides a simple
programmatic API as well as a CLI for testing / integration.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import redirect_stdout
from io import StringIO
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from dizibox_scraper import DiziboxScraper
from hdfilm_scraper import HDFilmScraper

SUPPORTED_SITES = ("dizibox", "hdfilm")


def detect_site(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    hostname = hostname.lower()
    if "dizibox" in hostname:
        return "dizibox"
    if "hdfilmcehennemi" in hostname:
        return "hdfilm"
    raise ValueError(f"Unsupported hostname: {hostname}")


def resolve_stream(
    url: str,
    site: Optional[str] = None,
    *,
    headless: bool = True,
    quiet: bool = False,
) -> Dict[str, Any]:
    """
    Resolve a streaming page URL into playable stream metadata.

    Parameters
    ----------
    url: str
        Target page URL (episode/movie page).
    site: Optional[str]
        Optional explicit site hint ("dizibox" or "hdfilm").
    headless: bool
        Run browser automation in headless mode.
    quiet: bool
        When True, suppress stdout noise from the underlying scrapers.
    """
    site = site or detect_site(url)
    if site not in SUPPORTED_SITES:
        raise ValueError(f"Unsupported site: {site}")

    buffer = StringIO()
    result: Optional[Dict[str, Any]] = None
    original_stdout = sys.stdout
    default_stdout = sys.__stdout__

    if quiet:
        try:
            with redirect_stdout(buffer):
                if site == "dizibox":
                    scraper = DiziboxScraper(headless=headless)
                    result = scraper.get_stream_url(url)
                elif site == "hdfilm":
                    scraper = HDFilmScraper(headless=headless)
                    result = scraper.get_stream_info(url)
        except ValueError as exc:
            # Some scripts manipulate sys.stdout; fall back to verbose mode
            print(f"[resolver] quiet mode failed ({exc}), retrying with verbose output.")
            quiet = False

    if not result and not quiet:
        if site == "dizibox":
            scraper = DiziboxScraper(headless=headless)
            result = scraper.get_stream_url(url)
        elif site == "hdfilm":
            scraper = HDFilmScraper(headless=headless)
            result = scraper.get_stream_info(url)
    # Restore stdout in case scrapers modified it
    sys.stdout = original_stdout if original_stdout and not getattr(original_stdout, "closed", False) else default_stdout

    debug_output = buffer.getvalue() if quiet else ""

    if not result:
        raise RuntimeError(f"Failed to resolve stream for site={site} url={url}")

    return {
        "site": site,
        "url": url,
        "result": result,
        "log": debug_output,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve a streaming URL on-demand.")
    parser.add_argument("url", help="Episode or movie page URL to resolve")
    parser.add_argument(
        "--site",
        choices=SUPPORTED_SITES,
        help="Optional explicit site hint (otherwise detected from hostname)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser automation in headed mode for debugging",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print scraper logs to stdout",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional path to write JSON result (defaults to stdout)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = resolve_stream(
        args.url,
        site=args.site,
        headless=not args.headed,
        quiet=not args.verbose,
    )
    output_json = json.dumps(data, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output_json)
        print(f"[resolver] wrote result to {args.output}")
    else:
        os.write(1, (output_json + "\n").encode("utf-8", "replace"))


if __name__ == "__main__":
    main()
