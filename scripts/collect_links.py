#!/usr/bin/env python3
"""
Collect page URLs from supported Turkish streaming sites.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent

HDFILM_BASE = "https://www.hdfilmcehennemi.la"
HDFILM_SITEMAP_INDEX = f"{HDFILM_BASE}/sitemap.xml"

DIZIBOX_BASE = "https://www.dizibox.live"
DIZIBOX_ARCHIVE = f"{DIZIBOX_BASE}/arsiv/"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
        "Gecko/20100101 Firefox/121.0"
    )
}


@dataclass
class CollectionResult:
    site: str
    urls: List[str]

    def to_json(self) -> str:
        payload = {
            "site": self.site,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "count": len(self.urls),
            "urls": self.urls,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)


def _parse_cache_timestamp(value: object) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            try:
                return datetime.fromisoformat(value).timestamp()
            except ValueError:
                return None
    return None


def load_sitemap_cache(cache_path: Optional[Path]) -> Dict[str, Dict[str, object]]:
    if cache_path is None or not cache_path.exists():
        return {}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception as exc:
        print(f"[hdfilm] unable to load sitemap cache: {exc}", file=sys.stderr)
    return {}


def save_sitemap_cache(cache_path: Path, cache_data: Dict[str, Dict[str, object]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(cache_data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(cache_path)


def fetch_text(session: requests.Session, url: str) -> str:
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def iter_hdfilm_sitemaps(session: requests.Session) -> Iterable[str]:
    from xml.etree import ElementTree as ET

    root = ET.fromstring(fetch_text(session, HDFILM_SITEMAP_INDEX))
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    for node in root.findall("sm:sitemap", ns):
        loc = node.find("sm:loc", ns)
        if loc is not None and loc.text:
            yield loc.text.strip()


def extract_hdfilm_urls(session: requests.Session, sitemap_urls: Iterable[str]) -> Set[str]:
    allowed: Set[str] = set()
    exclude_prefixes = {
        "category",
        "dil",
        "etiket",
        "film-robotu-1",
        "gizlilik-politikasi",
        "hakkimizda",
        "iletisim",
        "imdb-7-puan-uzeri-filmler-1",
        "en-cok-yorumlananlar-2",
        "en-cok-begenilen-filmleri-izle-2",
        "kullanim-kosullari",
        "serifilmlerim-3",
        "tur",
        "uye-girisi",
        "uye-ol",
        "yabancidiziizle-5",
        "yil",
        "rss",
        "sitemap",
        "blog",
        "arsiv",
    }
    base_netloc = urlparse(HDFILM_BASE).netloc
    loc_pattern = re.compile(r"<loc>(https://www\.hdfilmcehennemi\.la/[^<]+)</loc>", re.IGNORECASE)
    for sm_url in sitemap_urls:
        try:
            xml_text = fetch_text(session, sm_url)
        except Exception as exc:
            print(f"[hdfilm] failed to fetch {sm_url}: {exc}", file=sys.stderr)
            continue
        matches = loc_pattern.findall(xml_text)
        if not matches:
            print(f"[hdfilm] no <loc> entries found in {sm_url}", file=sys.stderr)
        for loc in matches:
            parsed = urlparse(loc.strip())
            if parsed.netloc != base_netloc:
                continue
            path = parsed.path.strip("/")
            if not path or "/" in path:
                continue
            slug = path.lower()
            if slug in exclude_prefixes or slug.startswith(("category-", "tur-", "etiket-", "yil-")):
                continue
            allowed.add(loc)
    return allowed


SHOW_LINK_PATTERN = re.compile(
    r'href="(?:(?:https?:)?//www\.dizibox\.live)?(/diziler/[^"?#]+/)"',
    re.IGNORECASE,
)
EPISODE_LINK_PATTERN = re.compile(
    r'href="(?:(?:https?:)?//www\.dizibox\.live)?(/[^"?#]+-bolum-izle/)"',
    re.IGNORECASE,
)


def extract_links(pattern: re.Pattern, html: str, base: str) -> Set[str]:
    matches = pattern.findall(html)
    return {urljoin(base, m) for m in matches}


def collect_dizibox_shows(context) -> List[str]:
    page = context.new_page()
    page.goto(DIZIBOX_BASE, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    resp = context.request.get(DIZIBOX_ARCHIVE)
    if resp.status != 200:
        raise RuntimeError(f"Archive request failed with status {resp.status}")
    html = resp.text()
    show_urls = sorted(extract_links(SHOW_LINK_PATTERN, html, DIZIBOX_BASE))
    print(f"[dizibox] found {len(show_urls)} show pages")
    page.close()
    return show_urls


def collect_dizibox_episodes(max_shows: int | None = None) -> Set[str]:
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=REQUEST_HEADERS["User-Agent"],
            locale="tr-TR",
        )
        shows = collect_dizibox_shows(context)
        if max_shows:
            shows = shows[:max_shows]
        episodes: Set[str] = set()
        try:
            for idx, show_url in enumerate(shows, 1):
                try:
                    resp = context.request.get(show_url, timeout=60000)
                except Exception as exc:
                    print(f"[dizibox] request failed for {show_url}: {exc}", file=sys.stderr)
                    continue
                if resp.status != 200:
                    print(f"[dizibox] status {resp.status} for {show_url}", file=sys.stderr)
                    continue
                html = resp.text()
                new_links = extract_links(EPISODE_LINK_PATTERN, html, DIZIBOX_BASE)
                episodes.update(new_links)
                if idx % 50 == 0 or idx == len(shows):
                    print(f"[dizibox] processed {idx}/{len(shows)} shows, episodes: {len(episodes)}")
                time.sleep(0.2)
        finally:
            context.close()
            browser.close()
        return episodes


def collect_hdfilm(
    limit: int | None = None,
    *,
    cache_path: Optional[Path] = None,
    cache_ttl: float = 0.0,
    delay: float = 0.0,
) -> Set[str]:
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    sitemap_urls = list(iter_hdfilm_sitemaps(session))
    if limit is not None:
        sitemap_urls = sitemap_urls[:limit]

    cache_data: Dict[str, Dict[str, object]] = load_sitemap_cache(cache_path)
    now_ts = time.time()
    ttl_seconds = max(cache_ttl or 0.0, 0.0)
    collected: Set[str] = set()
    skipped = 0
    fetched = 0

    print(f"[hdfilm] scanning {len(sitemap_urls)} sitemap files")
    for idx, sitemap_url in enumerate(sitemap_urls, 1):
        cached_entry = cache_data.get(sitemap_url) if cache_data else None
        use_cache = False
        if cached_entry and ttl_seconds > 0:
            cached_ts = _parse_cache_timestamp(cached_entry.get("checked_at"))
            if cached_ts is not None and (now_ts - cached_ts) < ttl_seconds:
                urls = cached_entry.get("urls") or []
                if isinstance(urls, list):
                    collected.update(urls)
                use_cache = True
                skipped += 1

        if use_cache:
            continue

        urls = extract_hdfilm_urls(session, [sitemap_url])
        fetched += 1
        collected.update(urls)
        if cache_path is not None:
            cache_data[sitemap_url] = {
                "checked_at": now_ts,
                "urls": sorted(urls),
            }
        if delay > 0 and idx < len(sitemap_urls):
            time.sleep(delay)

    if cache_path is not None:
        save_sitemap_cache(cache_path, cache_data)

    print(f"[hdfilm] fetched {fetched} sitemap files ({skipped} served from cache)")
    return collected


def write_output(result: CollectionResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.to_json(), encoding="utf-8")
    print(f"[output] wrote {len(result.urls)} URLs to {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect page URLs from supported sites.")
    parser.add_argument("--site", choices=["hdfilm", "dizibox"], required=True, help="Site to scrape")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for HDFilm sitemaps")
    parser.add_argument("--max-shows", type=int, default=None, help="Optional cap on number of Dizibox shows")
    parser.add_argument(
        "--sitemap-cache",
        type=Path,
        default=None,
        help="Optional cache file for HDFilm sitemap fetches (default: data/hdfilm_sitemap_cache.json when caching is enabled)",
    )
    parser.add_argument(
        "--sitemap-ttl",
        type=float,
        default=86400.0,
        help="Seconds to reuse cached HDFilm sitemap entries before refetching (default: 86400, set to 0 to always refetch)",
    )
    parser.add_argument(
        "--sitemap-delay",
        type=float,
        default=0.0,
        help="Delay in seconds between HDFilm sitemap requests",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (defaults to data/<site>_links.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.site == "hdfilm":
        cache_path = args.sitemap_cache
        if cache_path is None and args.sitemap_ttl and args.sitemap_ttl > 0:
            cache_path = ROOT_DIR / "data" / "hdfilm_sitemap_cache.json"
        urls = sorted(
            collect_hdfilm(
                limit=args.limit,
                cache_path=cache_path,
                cache_ttl=max(args.sitemap_ttl, 0.0),
                delay=max(args.sitemap_delay, 0.0),
            )
        )
    else:
        urls = sorted(collect_dizibox_episodes(max_shows=args.max_shows))

    output_path = args.output or (ROOT_DIR / "data" / f"{args.site}_links.json")
    write_output(CollectionResult(site=args.site, urls=urls), output_path)


if __name__ == "__main__":
    main()
