#!/usr/bin/env python3
"""
Catalog store helper for resolver API and STRM generation.

Loads the catalog JSON and exposes simple lookup utilities.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

CatalogEntry = Dict[str, object]


def load_catalog(path: Path) -> Dict[str, CatalogEntry]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    index: Dict[str, CatalogEntry] = {}
    for entry in data:
        entry_id = entry.get("id")
        if entry_id:
            index[str(entry_id)] = entry
    return index


def save_catalog(path: Path, entries: Dict[str, CatalogEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = list(entries.values())
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def get_entry(catalog: Dict[str, CatalogEntry], entry_id: str) -> Optional[CatalogEntry]:
    return catalog.get(entry_id)
