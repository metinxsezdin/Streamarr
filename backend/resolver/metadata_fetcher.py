"""
TMDB metadata fetcher helper.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()


class MetadataFetcher:
    TMDB_ENDPOINT = "https://api.themoviedb.org/3"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("TMDB_KEY")
        self.enabled = bool(self.api_key)

    def enrich(self, title: str, entry_type: str, site: str) -> Dict[str, object]:
        if not self.enabled or not title:
            return {}

        data: Optional[Dict[str, object]]
        if entry_type == "movie":
            data = self.search_movie(title)
        else:
            data = self.search_tv(title)

        if not data:
            return {}

        return {
            "tmdb_id": data.get("id"),
            "title": data.get("title") or data.get("name") or title,
            "original_title": data.get("original_title") or data.get("original_name") or title,
            "year": self._extract_year(data.get("release_date") or data.get("first_air_date")),
            "poster": self._build_image_url(data.get("poster_path")),
            "backdrop": self._build_image_url(data.get("backdrop_path")),
            "overview": (data.get("overview") or "").strip(),
        }

    def _build_image_url(self, path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        return f"https://image.tmdb.org/t/p/w500{path}"

    def _extract_year(self, date_str: Optional[str]) -> int:
        if not date_str:
            return 0
        try:
            return int(date_str.split("-")[0])
        except Exception:
            return 0

    @lru_cache(maxsize=256)
    def search_movie(self, title: str) -> Optional[Dict[str, object]]:
        params = {
            "api_key": self.api_key,
            "query": title,
            "include_adult": "false",
            "language": "tr-TR",
        }
        resp = requests.get(f"{self.TMDB_ENDPOINT}/search/movie", params=params, timeout=20)
        if resp.status_code != 200:
            return None
        results = resp.json().get("results") or []
        return results[0] if results else None

    @lru_cache(maxsize=256)
    def search_tv(self, title: str) -> Optional[Dict[str, object]]:
        params = {
            "api_key": self.api_key,
            "query": title,
            "include_adult": "false",
            "language": "tr-TR",
        }
        resp = requests.get(f"{self.TMDB_ENDPOINT}/search/tv", params=params, timeout=20)
        if resp.status_code != 200:
            return None
        results = resp.json().get("results") or []
        return results[0] if results else None
