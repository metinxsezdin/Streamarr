#!/usr/bin/env python3
"""
Build a minimal metadata catalog for STRM generation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR / "backend"))

from resolver.metadata_fetcher import MetadataFetcher  # noqa: E402


@dataclass
class CatalogEntry:
    id: str
    site: str
    title: str
    subtitle: str
    url: str
    year: int
    type: str
    original_title: str = ""
    poster: Optional[str] = None
    backdrop: Optional[str] = None
    overview: str = ""
    tmdb_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "site": self.site,
            "title": self.title,
            "subtitle": self.subtitle,
            "url": self.url,
            "year": self.year,
            "type": self.type,
            "original_title": self.original_title,
            "poster": self.poster,
            "backdrop": self.backdrop,
            "overview": self.overview,
            "tmdb_id": self.tmdb_id,
        }

    def apply_metadata(self, metadata: dict) -> None:
        if not metadata:
            return
        self.title = metadata.get("title", self.title)
        self.original_title = metadata.get("original_title", self.original_title)
        self.poster = metadata.get("poster", self.poster)
        self.backdrop = metadata.get("backdrop", self.backdrop)
        self.overview = metadata.get("overview", self.overview)
        self.tmdb_id = metadata.get("tmdb_id", self.tmdb_id)
        year = metadata.get("year")
        if isinstance(year, int) and year:
            self.year = year


DIZIBOX_EPISODE_RE = re.compile(
    r"https://www\.dizibox\.live/(?P<slug>.+)-(?P<season>\d+)-sezon-(?P<episode>\d+)-bolum(?:-.*)?/?"
)
HDFILM_MOVIE_RE = re.compile(r"https://www\.hdfilmcehennemi\.la/(?P<slug>[-a-z0-9]+)/?")


def load_urls(file_path: Path) -> Iterable[str]:
    if not file_path.exists():
        return []
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "urls" in data:
        return data["urls"]
    if isinstance(data, list):
        return data
    return []


def build_dizibox_catalog(urls: Iterable[str]) -> List[CatalogEntry]:
    entries: List[CatalogEntry] = []
    for url in urls:
        match = DIZIBOX_EPISODE_RE.match(url)
        if not match:
            continue
        slug = match.group("slug")
        season = int(match.group("season"))
        episode = int(match.group("episode"))
        title_guess = " ".join(slug.split("-")).title()
        entry_id = f"dizibox:{slug}:s{season:02d}e{episode:02d}"
        subtitle = f"Sezon {season} Bölüm {episode}"
        entries.append(
            CatalogEntry(
                id=entry_id,
                site="dizibox",
                title=title_guess,
                subtitle=subtitle,
                url=url,
                year=0,
                type="episode",
            )
        )
    return entries


def build_hdfilm_catalog(urls: Iterable[str]) -> List[CatalogEntry]:
    entries: List[CatalogEntry] = []
    slug_cache: set[str] = set()
    for url in urls:
        match = HDFILM_MOVIE_RE.match(url)
        if not match:
            continue
        slug = match.group("slug")
        if slug in slug_cache:
            continue
        slug_cache.add(slug)
        title_guess = " ".join(slug.split("-")).title()
        entry_id = f"hdfilm:{slug}"
        entries.append(
            CatalogEntry(
                id=entry_id,
                site="hdfilm",
                title=title_guess,
                subtitle="Film",
                url=url,
                year=0,
                type="movie",
            )
        )
    return entries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build catalog JSON for STRM generation.")
    parser.add_argument(
        "--hdfilm-source",
        type=Path,
        default=ROOT_DIR / "data/hdfilm_links_sample.json",
        help="Path to JSON list of HDFilm URLs",
    )
    parser.add_argument(
        "--dizibox-source",
        type=Path,
        default=ROOT_DIR / "data/dizibox_links_sample.json",
        help="Path to JSON list of Dizibox URLs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "data/catalog.json",
        help="Output catalog JSON path",
    )
    parser.add_argument(
        "--tmdb-key",
        type=str,
        default=os.environ.get("TMDB_KEY"),
        help="TMDB API key (falls back to TMDB_KEY env var)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fetcher = MetadataFetcher(api_key=args.tmdb_key)
    hdfilm_urls = load_urls(args.hdfilm_source)
    dizibox_urls = load_urls(args.dizibox_source)

    entries: List[CatalogEntry] = []
    entries.extend(build_hdfilm_catalog(hdfilm_urls))
    entries.extend(build_dizibox_catalog(dizibox_urls))

    if fetcher.enabled:
        for entry in entries:
            metadata = fetcher.enrich(entry.title, entry.type, entry.site)
            entry.apply_metadata(metadata)
    else:
        print("[catalog] TMDB key missing; skipping metadata enrichment")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    data = [entry.to_dict() for entry in entries]
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[catalog] wrote {len(entries)} entries to {args.output}")


if __name__ == "__main__":
    main()
