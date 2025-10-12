"""
On-demand stream resolver for supported Turkish streaming sites.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .scrapers.dizibox import DiziboxScraper
from .scrapers.hdfilm import HDFilmScraper

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
    site = site or detect_site(url)
    if site not in SUPPORTED_SITES:
        raise ValueError(f"Unsupported site: {site}")

    if site == "dizibox":
        scraper = DiziboxScraper(headless=headless)
        result = scraper.get_stream_url(url)
    else:
        scraper = HDFilmScraper(headless=headless)
        result = scraper.get_stream_info(url)

    if not result:
        raise RuntimeError(f"Failed to resolve stream for site={site} url={url}")

    result.setdefault("page_url", url)

    return {
        "site": site,
        "url": url,
        "result": result,
        "log": "" if quiet else "",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve a streaming URL on-demand.")
    parser.add_argument("url", help="Episode or movie page URL to resolve")
    parser.add_argument("--site", choices=SUPPORTED_SITES, help="Optional explicit site hint")
    parser.add_argument("--headed", action="store_true", help="Run browser automation in headed mode")
    parser.add_argument("--verbose", action="store_true", help="Print scraper logs to stdout")
    parser.add_argument("--output", type=str, help="Optional path to write JSON result (defaults to stdout)")
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
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(output_json)
        print(f"[resolver] wrote result to {args.output}")
    else:
        os.write(1, (output_json + "\n").encode("utf-8", "replace"))


if __name__ == "__main__":
    main()
