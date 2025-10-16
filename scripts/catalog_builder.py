#!/usr/bin/env python3
"""
Build a unified metadata catalog with multi-source support for STRM generation.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sqlite3
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests

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
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
        "Gecko/20100101 Firefox/121.0"
    )
}
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


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
        or (
            cleaned[-1].isdigit()
            and len(cleaned[-1]) <= 2
            and len(cleaned) > 1
            and not cleaned[-2].isdigit()
        )
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

    result = list(filtered or tokens)
    while result and result[0] == "1":
        result.pop(0)
    return result


def _merge_possessive_tokens(tokens: List[str]) -> List[str]:
    merged: List[str] = []
    for token in tokens:
        if (
            token == "s"
            and merged
            and not merged[-1].isdigit()
            and not merged[-1].endswith("'s")
        ):
            merged[-1] = merged[-1] + "'s"
        else:
            merged.append(token)
    return merged


def guess_title_from_slug(slug: str) -> str:
    tokens = _clean_slug_tokens(slug)
    tokens = _merge_possessive_tokens(tokens)
    if not tokens:
        return slug.replace("-", " ").strip().title()

    if all(token.isdigit() for token in tokens):
        return "-".join(tokens)

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


def _clean_site_title(site: str, raw_title: str, slug: Optional[str] = None) -> str:
    title = raw_title.strip()
    if not title:
        return raw_title

    def _strip_suffix(text: str, patterns: List[str]) -> str:
        lowered = text.lower()
        for pattern in patterns:
            if lowered.endswith(pattern):
                return text[: -len(pattern)].rstrip(" -|")
        return text

    title = html.unescape(title)
    title = re.sub(r"\s+", " ", title).strip()

    if slug:
        slug_tokens = [token for token in slug.split("-") if token]
        if slug_tokens and slug_tokens[0] == "1":
            stripped = re.sub(r"^[1]+\s+", "", title).strip()
            if stripped:
                title = stripped

    if site == "hdfilm":
        title = re.sub(r"\s*[\-|]\s*HD\s*Film.*$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*\|\s*HDFilm.*$", "", title, flags=re.IGNORECASE)
        title = _strip_suffix(title, [" izle", " hd izle", " full izle", " hd film"])
    elif site == "dizibox":
        title = re.sub(r"\s*[\-|]\s*Dizibox.*$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*\|\s*Dizibox.*$", "", title, flags=re.IGNORECASE)
        title = _strip_suffix(
            title,
            [
                " izle",
                " full izle",
                " bolum izle",
                " bölüm izle",
            ],
        )
    else:
        title = _strip_suffix(title, [" izle", " full izle", " full i̇zle"])

    return title.strip(" -|") or raw_title.strip()


def fetch_page_title(
    session: requests.Session,
    site: str,
    url: str,
    slug: Optional[str] = None,
    timeout: float = 15.0,
) -> Optional[str]:
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return None
    text = response.text
    match = TITLE_RE.search(text)
    if not match:
        return None
    raw_title = match.group(1)
    if not raw_title:
        return None
    return _clean_site_title(site, raw_title, slug=slug)


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


def persist_catalog_sqlite(entries: List[CatalogEntry], sqlite_path: Path) -> None:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(
            """
CREATE TABLE IF NOT EXISTS media_items (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    original_title TEXT,
    subtitle TEXT,
    year INTEGER,
    overview TEXT,
    poster TEXT,
    backdrop TEXT,
    tmdb_id INTEGER,
    site TEXT NOT NULL,
    url TEXT NOT NULL,
    season INTEGER,
    episode INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS media_sources (
    media_id TEXT NOT NULL,
    site TEXT NOT NULL,
    url TEXT NOT NULL,
    site_entry_id TEXT,
    priority INTEGER,
    is_primary INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE,
    PRIMARY KEY (media_id, site, url)
);

CREATE INDEX IF NOT EXISTS idx_media_items_type_title
    ON media_items(type, title);

CREATE INDEX IF NOT EXISTS idx_media_items_tmdb
    ON media_items(tmdb_id);

CREATE INDEX IF NOT EXISTS idx_media_sources_priority
    ON media_sources(media_id, priority, site);
"""
        )
        with conn:
            conn.execute("DELETE FROM media_sources;")
            conn.execute("DELETE FROM media_items;")

            item_sql = """
INSERT INTO media_items (
    id, type, title, original_title, subtitle, year, overview, poster, backdrop,
    tmdb_id, site, url, season, episode, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
"""
            items_payload = []
            for entry in entries:
                year_value = entry.year if entry.year else None
                items_payload.append(
                    (
                        entry.id,
                        entry.type,
                        entry.title,
                        entry.original_title or None,
                        entry.subtitle or None,
                        year_value,
                        entry.overview or None,
                        entry.poster or None,
                        entry.backdrop or None,
                        entry.tmdb_id,
                        entry.site,
                        entry.url,
                        entry.season,
                        entry.episode,
                    )
                )
            conn.executemany(item_sql, items_payload)

            source_sql = """
INSERT INTO media_sources (
    media_id, site, url, site_entry_id, priority, is_primary
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(media_id, site, url) DO UPDATE SET
    site_entry_id=excluded.site_entry_id,
    priority=excluded.priority,
    is_primary=excluded.is_primary;
"""
            sources_payload: List[tuple] = []
            for entry in entries:
                for source in entry.sources:
                    is_primary = 1 if source.site == entry.site and source.url == entry.url else 0
                    sources_payload.append(
                        (
                            entry.id,
                            source.site,
                            source.url,
                            source.site_entry_id,
                            source.priority,
                            is_primary,
                        )
                    )
            if sources_payload:
                conn.executemany(source_sql, sources_payload)
    print(f"[catalog] wrote {len(entries)} entries to {sqlite_path}")


def persist_catalog(
    entries: List[CatalogEntry],
    output_path: Optional[Path],
    *,
    chunk_size: Optional[int] = None,
    sqlite_path: Optional[Path] = None,
    write_json: bool = True,
) -> None:
    if write_json:
        if output_path is None:
            raise ValueError("output_path must be provided when write_json is True")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        stem = output_path.stem
        suffix = output_path.suffix or ".json"

        type_labels = {"movie": "movies"}
        partitions: Dict[str, List[CatalogEntry]] = {}
        for entry in entries:
            label = type_labels.get(entry.type, "episodes")
            partitions.setdefault(label, []).append(entry)

        for label, partition in partitions.items():
            if not partition:
                continue
            label_stem = f"{stem}.{label}"
            if not chunk_size or chunk_size <= 0:
                payload = [entry.to_dict() for entry in partition]
                chunk_path = output_path.with_name(f"{label_stem}{suffix}")
                tmp_path = chunk_path.with_suffix(chunk_path.suffix + ".tmp")
                tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
                tmp_path.replace(chunk_path)
                print(f"[catalog] wrote {len(partition)} {label} entries to {chunk_path}")
            else:
                total_chunks = (len(partition) + chunk_size - 1) // chunk_size
                for index, start in enumerate(range(0, len(partition), chunk_size), 1):
                    chunk_entries = partition[start : start + chunk_size]
                    payload = [entry.to_dict() for entry in chunk_entries]
                    chunk_name = f"{label_stem}.{index:03d}{suffix}"
                    chunk_path = output_path.with_name(chunk_name)
                    tmp_path = chunk_path.with_suffix(chunk_path.suffix + ".tmp")
                    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
                    tmp_path.replace(chunk_path)
                    print(f"[catalog] wrote {label} chunk {index}/{total_chunks}: {chunk_path}")
                print(
                    f"[catalog] completed JSON export for {label} "
                    f"({len(partition)} entries across {total_chunks} files)"
                )

    if sqlite_path is not None:
        persist_catalog_sqlite(entries, sqlite_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build catalog JSON for STRM generation.")
    parser.add_argument(
        "--hdfilm-source",
        type=Path,
        default=ROOT_DIR / "data/hdfilm_links.json",
        help="Path to JSON list of HDFilm URLs (defaults to data/hdfilm_links.json)",
    )
    parser.add_argument(
        "--dizibox-source",
        type=Path,
        default=ROOT_DIR / "data/dizibox_links.json",
        help="Path to JSON list of Dizibox URLs (defaults to data/dizibox_links.json)",
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
    parser.add_argument(
        "--sqlite-db",
        type=Path,
        help="Optional SQLite database path for catalog persistence (e.g., data/catalog.sqlite)",
    )
    parser.add_argument(
        "--skip-json",
        action="store_true",
        help="Skip writing JSON output (useful when only SQLite export is desired)",
    )
    parser.add_argument(
        "--fetch-html-titles",
        action="store_true",
        help="Fetch <title> tags from source pages to improve initial titles",
    )
    parser.add_argument(
        "--title-fetch-limit",
        type=int,
        help="Optional limit on the number of HTML title fetches (for testing/troubleshooting)",
    )
    parser.add_argument(
        "--title-fetch-timeout",
        type=float,
        default=15.0,
        help="Per-request timeout in seconds when fetching HTML titles (default: 15.0)",
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

    if args.fetch_html_titles:
        session = requests.Session()
        session.headers.update(REQUEST_HEADERS)
        title_requests = 0
        updated_titles = 0
        for idx, entry in enumerate(raw_entries, 1):
            if args.title_fetch_limit is not None and title_requests >= args.title_fetch_limit:
                break
            title = fetch_page_title(
                session,
                entry.site,
                entry.url,
                slug=entry.show_slug,
                timeout=args.title_fetch_timeout,
            )
            title_requests += 1
            if title:
                if title != entry.title:
                    entry.title = title
                    updated_titles += 1
            if idx % 100 == 0:
                print(f"[catalog] fetched HTML titles for {title_requests} entries (updated {updated_titles})")
        print(f"[catalog] HTML title fetch complete: requests={title_requests}, updated={updated_titles}")

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
    if args.skip_json and not args.sqlite_db:
        print("[catalog] --skip-json specified without --sqlite-db; no output will be written")
    persist_catalog(
        grouped_entries,
        None if args.skip_json else args.output,
        chunk_size=args.chunk_size,
        sqlite_path=args.sqlite_db,
        write_json=not args.skip_json,
    )


if __name__ == "__main__":
    main()
