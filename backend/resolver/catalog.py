"""
Helpers for loading the catalog JSON used by the resolver API.
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


def get_entry(catalog: Dict[str, CatalogEntry], entry_id: str) -> Optional[CatalogEntry]:
    return catalog.get(entry_id)
