#!/usr/bin/env python3
"""
Build a unified metadata catalog with multi-source support for STRM generation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR / "backend"))

from resolver.metadata_fetcher import MetadataFetcher  # noqa: E402

# Lower number means higher priority when picking the primary source.
SITE_PRIORITY: Dict[str, int] = {
    "hdfilm": 10,
    "dizibox": 20,
    "dizipub": 30,
    "dizipal": 40,
    "dizilla": 50,
}
DEFAULT_SITE_PRIORITY = 100

TITLE_STOPWORDS = {
    "izle",
    "izler",
    "izlemek",
    "hd",
    "hdf",
    "full",
    "tek",
    "parca",
    "tekparca",
    "part",
    "fragman",
    "fragmani",
    "fragmanini",
    "film",
    "belgesel",
    "dizi",
    "bolum",
    "seyret",
    "seyretmek",
    "watch",
    "online",
    "bedava",
    "ucretsiz",
    "turkce",
    "dublaj",
    "altyazili",
    "tr",
    "1080p",
    "720p",
    "480p",
    "360p",
    "uhd",
    "4k",
    "hdr",
}

TOKEN_REPLACEMENTS = {
    "mhz": "MHz",
    "khz": "kHz",
    "ghz": "GHz",
    "3d": "3D",
    "4k": "4K",
    "uhd": "UHD",
    "hdr": "HDR",
}

ROMAN_NUMERALS = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
SUFFIX_KEEP_BASES = {"part", "bolum", "episode"}


def _site_priority(site: str) -> int:
    return SITE_PRIORITY.get(site, DEFAULT_SITE_PRIORITY)


def _normalize_key_component(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return cleaned or "unknown"


def _clean_slug_tokens(slug: str) -> List[str]:
    tokens = [token for token in slug.lower().split("-") if token]
    if not tokens:
        return []

    cleaned = tokens[:]
    while cleaned and (
        cleaned[-1] in TITLE_STOPWORDS
        or (cleaned[-1].isdigit() and len(cleaned[-1]) <= 2 and len(cleaned) > 1)
        or re.fullmatch(r"\d{3,4}p", cleaned[-1])
    ):
        cleaned.pop()

    if not cleaned:
        cleaned = tokens[:]

    filtered: List[str] = []
    for token in cleaned:
        if token in TITLE_STOPWORDS:
            continue
        if re.fullmatch(r"\d{3,4}p", token):
            continue
        filtered.append(token)

    return filtered or tokens


def guess_title_from_slug(slug: str) -> str:
    tokens = _clean_slug_tokens(slug)
    if not tokens:
        return slug.replace("-", " ").strip().title()

    words: List[str] = []
    for token in tokens:
        mapped = TOKEN_REPLACEMENTS.get(token)
        if mapped:
            words.append(mapped)
            continue

        if token in ROMAN_NUMERALS:
            words.append(token.upper())
            continue

        if token.isdigit():
            words.append(token)
            continue

        match = re.match(r"^(.*?)(\d+)$", token)
        if match and match.group(1) and match.group(2):
            base = match.group(1)
            number = match.group(2)
            if base in TITLE_STOPWORDS and base not in SUFFIX_KEEP_BASES:
                words.append(number)
                continue
            token = f"{base} {number}"

        normalized = re.sub(r"[_]+", " ", token)
        normalized = normalized.replace("  ", " ").strip()
        if not normalized:
            continue
        words.append(" ".join(part.capitalize() for part in normalized.split()))

    if len(words) >= 2 and words[0].isdigit() and words[1].isdigit():
        if words[0] == words[1]:
            words[0] = f"{words[0]}.{words[1]}"
            words.pop(1)

    title = " ".join(words).strip()
    if not title:
        title = slug.replace("-", " ").strip()
    return title


@dataclass
class SourceLink:
    site: str
    url: str
    site_entry_id: str
    priority: int = field(default=DEFAULT_SITE_PRIORITY)

    def to_dict(self) -> dict:
        return {
            "site": self.site,
            "url": self.url,
            "site_entry_id": self.site_entry_id,
            "priority": self.priority,
        }


@dataclass
class RawEntry:
    id: str
    site: str
    title: str
    subtitle: str
    url: str
    year: int
    type: str
    season: Optional[int] = None
    episode: Optional[int] = None
    original_title: str = ""
    poster: Optional[str] = None
    backdrop: Optional[str] = None
    overview: str = ""
    tmdb_id: Optional[int] = None
    show_slug: Optional[str] = None

    def apply_metadata(self, metadata: Dict[str, object]) -> None:
        if not metadata:
            return

        title = metadata.get("title")
        if isinstance(title, str) and title:
            self.title = title
        original_title = metadata.get("original_title")
        if isinstance(original_title, str) and original_title:
            self.original_title = original_title
        overview = metadata.get("overview")
        if isinstance(overview, str) and overview:
            self.overview = overview
        poster = metadata.get("poster")
        if isinstance(poster, str) and poster:
            self.poster = poster
        backdrop = metadata.get("backdrop")
        if isinstance(backdrop, str) and backdrop:
            self.backdrop = backdrop
        year = metadata.get("year")
        if isinstance(year, int) and year:
            self.year = year
        tmdb = metadata.get("tmdb_id")
        if isinstance(tmdb, int) and tmdb > 0:
            self.tmdb_id = tmdb

    def canonical_key(self) -> str:
        if self.type == "movie":
            if self.tmdb_id:
                return f"movie:tmdb:{self.tmdb_id}"
            base = _normalize_key_component(self.original_title or self.title)
            year_part = f":y{self.year}" if self.year else ""
            return f"movie:title:{base}{year_part}"

        season = self.season if self.season is not None else 0
        episode = self.episode if self.episode is not None else 0
        if self.tmdb_id:
            return f"episode:tmdb:{self.tmdb_id}:s{season:02d}e{episode:02d}"
        slug = self.show_slug or _normalize_key_component(self.title)
        return f"episode:slug:{slug}:s{season:02d}e{episode:02d}"

    def build_source(self) -> SourceLink:
        return SourceLink(
            site=self.site,
            url=self.url,
            site_entry_id=self.id,
            priority=_site_priority(self.site),
        )

    def search_candidates(self) -> List[str]:
        candidates: List[str] = []

        def _add(value: Optional[str]) -> None:
            if not value:
                return
            normalized = value.strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)

        _add(self.title)
        _add(self.original_title)

        slug_sources: List[str] = []
        if self.show_slug:
            slug_sources.append(self.show_slug)

        if self.id:
            slug_parts = [
                part
                for part in self.id.split(":")
                if part
                and part != self.site
                and not re.fullmatch(r"s\d+e\d+", part, flags=re.IGNORECASE)
            ]
            slug_sources.extend(slug_parts)

        for slug in slug_sources:
            candidate = guess_title_from_slug(slug)
            _add(candidate)
            plain = slug.replace("-", " ").strip()
            if plain:
                _add(" ".join(part.capitalize() for part in plain.split()))

        return candidates


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
    season: Optional[int] = None
    episode: Optional[int] = None
    sources: List[SourceLink] = field(default_factory=list)

    def merge_raw(self, raw: RawEntry) -> None:
        # Prefer richer metadata when available.
        if raw.title and (not self.title or _site_priority(raw.site) < _site_priority(self.site)):
            self.title = raw.title

        if raw.subtitle and not self.subtitle:
            self.subtitle = raw.subtitle

        if raw.original_title and not self.original_title:
            self.original_title = raw.original_title

        if raw.poster and not self.poster:
            self.poster = raw.poster

        if raw.backdrop and not self.backdrop:
            self.backdrop = raw.backdrop

        if raw.overview and not self.overview:
            self.overview = raw.overview

        if raw.tmdb_id and not self.tmdb_id:
            self.tmdb_id = raw.tmdb_id

        if raw.year and raw.year > 0 and (self.year == 0 or not self.year):
            self.year = raw.year

        if raw.season is not None:
            self.season = raw.season
        if raw.episode is not None:
            self.episode = raw.episode

        if not any(src.site == raw.site and src.url == raw.url for src in self.sources):
            self.sources.append(raw.build_source())
            self.sources.sort(key=lambda src: (src.priority, src.site))

        primary = self.sources[0]
        self.site = primary.site
        self.url = primary.url

    def to_dict(self) -> dict:
        data = {
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
            "sources": [source.to_dict() for source in self.sources],
        }
        if self.season is not None:
            data["season"] = self.season
        if self.episode is not None:
            data["episode"] = self.episode
        return data


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


def build_dizibox_entries(urls: Iterable[str]) -> List[RawEntry]:
    entries: List[RawEntry] = []
    for url in urls:
        match = DIZIBOX_EPISODE_RE.match(url)
        if not match:
            continue
        slug = match.group("slug")
        season = int(match.group("season"))
        episode = int(match.group("episode"))
        title_guess = guess_title_from_slug(slug)
        entry_id = f"dizibox:{slug}:s{season:02d}e{episode:02d}"
        subtitle = f"Sezon {season} Bolum {episode}"
        entries.append(
            RawEntry(
                id=entry_id,
                site="dizibox",
                title=title_guess,
                subtitle=subtitle,
                url=url,
                year=0,
                type="episode",
                season=season,
                episode=episode,
                show_slug=slug,
            )
        )
    return entries


def build_hdfilm_entries(urls: Iterable[str]) -> List[RawEntry]:
    entries: List[RawEntry] = []
    slug_cache: set[str] = set()
    for url in urls:
        match = HDFILM_MOVIE_RE.match(url)
        if not match:
            continue
        slug = match.group("slug")
        if slug in slug_cache:
            continue
        slug_cache.add(slug)
        title_guess = guess_title_from_slug(slug)
        entry_id = f"hdfilm:{slug}"
        entries.append(
            RawEntry(
                id=entry_id,
                site="hdfilm",
                title=title_guess,
                subtitle="Film",
                url=url,
                year=0,
                type="movie",
                show_slug=slug,
            )
        )
    return entries


def group_entries(raw_entries: List[RawEntry]) -> List[CatalogEntry]:
    index: Dict[str, CatalogEntry] = {}
    for raw in raw_entries:
        key = raw.canonical_key()
        entry = index.get(key)
        if entry is None:
            entry = CatalogEntry(
                id=key,
                site=raw.site,
                title=raw.title,
                subtitle=raw.subtitle,
                url=raw.url,
                year=raw.year,
                type=raw.type,
                original_title=raw.original_title,
                poster=raw.poster,
                backdrop=raw.backdrop,
                overview=raw.overview,
                tmdb_id=raw.tmdb_id,
                season=raw.season,
                episode=raw.episode,
                sources=[raw.build_source()],
            )
            index[key] = entry
        else:
            entry.merge_raw(raw)
    return sorted(
        index.values(),
        key=lambda e: (
            0 if e.type == "movie" else 1,
            _normalize_key_component(e.title),
            e.subtitle.lower(),
        ),
    )


def persist_catalog(entries: List[CatalogEntry], output_path: Path, chunk_size: Optional[int] = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not chunk_size or chunk_size <= 0:
        payload = [entry.to_dict() for entry in entries]
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(output_path)
        print(f"[catalog] wrote {len(entries)} entries to {output_path}")
        return

    stem = output_path.stem
    suffix = output_path.suffix or ".json"
    total_chunks = (len(entries) + chunk_size - 1) // chunk_size
    chunk_paths: List[Path] = []
    for index, start in enumerate(range(0, len(entries), chunk_size), 1):
        chunk_entries = entries[start : start + chunk_size]
        payload = [entry.to_dict() for entry in chunk_entries]
        chunk_name = f"{stem}.{index:03d}{suffix}"
        chunk_path = output_path.with_name(chunk_name)
        tmp_path = chunk_path.with_suffix(chunk_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(chunk_path)
        chunk_paths.append(chunk_path)
    print(f"[catalog] wrote {len(entries)} entries across {total_chunks} files:")
    for path in chunk_paths:
        print(f"  - {path}")


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
    parser.add_argument(
        "--max-hdfilm",
        type=int,
        help="Maximum number of HDFilm (movie) entries to include",
    )
    parser.add_argument(
        "--max-dizibox",
        type=int,
        help="Maximum number of Dizibox (episode) entries to include",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        help="Optional number of entries per output chunk; writes catalog.<NNN>.json files when set",
    )
    parser.add_argument(
        "--skip-tmdb",
        action="store_true",
        help="Skip TMDB metadata enrichment even if a key is configured",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fetcher = MetadataFetcher(api_key=args.tmdb_key)

    hdfilm_raw = list(build_hdfilm_entries(load_urls(args.hdfilm_source)))
    if args.max_hdfilm is not None:
        hdfilm_raw = hdfilm_raw[: max(args.max_hdfilm, 0)]

    dizibox_raw = list(build_dizibox_entries(load_urls(args.dizibox_source)))
    if args.max_dizibox is not None:
        dizibox_raw = dizibox_raw[: max(args.max_dizibox, 0)]

    raw_entries = [*hdfilm_raw, *dizibox_raw]
    print(f"[catalog] collected {len(raw_entries)} raw entries (movies={len(hdfilm_raw)}, episodes={len(dizibox_raw)})")

    metadata_enabled = fetcher.enabled and not args.skip_tmdb
    if metadata_enabled:
        for idx, entry in enumerate(raw_entries, 1):
            metadata: Dict[str, object] = {}
            for query in entry.search_candidates():
                metadata = fetcher.enrich(query, entry.type, entry.site)
                if metadata:
                    entry.apply_metadata(metadata)
                    break
            if not metadata:
                entry.apply_metadata({})
            if idx % 50 == 0 or idx == len(raw_entries):
                print(f"[catalog] enriched {idx}/{len(raw_entries)} entries")
    else:
        if args.skip_tmdb and fetcher.enabled:
            print("[catalog] TMDB enrichment explicitly disabled via --skip-tmdb")
        else:
            print("[catalog] TMDB key missing; skipping metadata enrichment")

    grouped_entries = group_entries(raw_entries)
    persist_catalog(grouped_entries, args.output, chunk_size=args.chunk_size)


if __name__ == "__main__":
    main()
