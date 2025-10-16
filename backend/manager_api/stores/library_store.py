"""Library store exposing read access to persisted catalog items."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlmodel import Session

from ..models import LibraryItemRecord
from ..schemas import (
    LibraryItemModel,
    LibraryListModel,
    LibraryMetricsModel,
    LibrarySortOption,
    StreamVariantModel,
)


@dataclass(slots=True)
class LibraryStore:
    """Read-oriented accessor for manager library items."""

    engine: Engine

    def list(
        self,
        *,
        query: str | None,
        sites: list[str] | None,
        item_type: str | None,
        year: int | None,
        year_min: int | None,
        year_max: int | None,
        has_tmdb: bool | None,
        sort: LibrarySortOption,
        page: int,
        page_size: int,
    ) -> LibraryListModel:
        """Return a paginated set of library items matching the provided filters."""

        offset = (page - 1) * page_size
        filters = []
        if query:
            filters.append(func.lower(LibraryItemRecord.title).like(f"%{query.lower()}%"))
        if sites:
            normalized_sites = sorted({site.lower() for site in sites if site})
            if normalized_sites:
                filters.append(func.lower(LibraryItemRecord.site).in_(normalized_sites))
        if item_type:
            filters.append(LibraryItemRecord.item_type == item_type)
        if year is not None:
            filters.append(LibraryItemRecord.year == year)
        if year_min is not None:
            filters.append(LibraryItemRecord.year.is_not(None))
            filters.append(LibraryItemRecord.year >= year_min)
        if year_max is not None:
            filters.append(LibraryItemRecord.year.is_not(None))
            filters.append(LibraryItemRecord.year <= year_max)
        if has_tmdb is True:
            filters.append(LibraryItemRecord.tmdb_id.is_not(None))
        elif has_tmdb is False:
            filters.append(LibraryItemRecord.tmdb_id.is_(None))

        count_statement = select(func.count()).select_from(LibraryItemRecord)
        items_statement = select(LibraryItemRecord)
        for condition in filters:
            count_statement = count_statement.where(condition)
            items_statement = items_statement.where(condition)

        sort_orders: dict[LibrarySortOption, tuple[object, ...]] = {
            "updated_desc": (LibraryItemRecord.updated_at.desc(), LibraryItemRecord.id),
            "updated_asc": (LibraryItemRecord.updated_at.asc(), LibraryItemRecord.id),
            "title_asc": (
                func.lower(LibraryItemRecord.title).asc(),
                LibraryItemRecord.id,
            ),
            "title_desc": (
                func.lower(LibraryItemRecord.title).desc(),
                LibraryItemRecord.id,
            ),
            "year_desc": (
                LibraryItemRecord.year.desc().nullslast(),
                func.lower(LibraryItemRecord.title).asc(),
            ),
            "year_asc": (
                LibraryItemRecord.year.asc().nullslast(),
                func.lower(LibraryItemRecord.title).asc(),
            ),
        }

        order_by_clauses = sort_orders.get(sort, sort_orders["updated_desc"])
        items_statement = items_statement.order_by(*order_by_clauses)

        items_statement = items_statement.offset(offset).limit(page_size)

        with Session(self.engine) as session:
            total = session.exec(count_statement).scalar_one()
            records: Sequence[LibraryItemRecord] = session.exec(items_statement).scalars().all()
            items = [_to_model(record) for record in records]

        return LibraryListModel(items=items, total=total, page=page, page_size=page_size)

    def get(self, item_id: str) -> LibraryItemModel | None:
        """Return metadata for a single library item if present."""

        with Session(self.engine) as session:
            record = session.get(LibraryItemRecord, item_id)
            return _to_model(record) if record else None

    def create(
        self,
        *,
        title: str,
        site: str,
        url: str,
        external_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> LibraryItemModel | None:
        """Create a new library item from catalog data."""

        # Check if item already exists
        with Session(self.engine) as session:
            existing = session.exec(
                select(LibraryItemRecord).where(LibraryItemRecord.external_id == external_id)
            ).first()
            
            if existing:
                return _to_model(existing)
            
            # Create new item
            record = LibraryItemRecord(
                id=uuid4().hex,
                title=title,
                site=site,
                url=url,
                external_id=external_id,
                item_type=metadata.get("type", "movie") if metadata else "movie",
                year=metadata.get("year") if metadata else None,
                tmdb_id=metadata.get("tmdb_id") if metadata else None,
                variants=[] if not metadata or not metadata.get("sources") else metadata.get("sources", []),
            )
            
            session.add(record)
            session.commit()
            session.refresh(record)
            return _to_model(record)

    def metrics(self) -> LibraryMetricsModel:
        """Return aggregate statistics for the catalog."""

        with Session(self.engine) as session:
            total = session.exec(
                select(func.count()).select_from(LibraryItemRecord)
            ).scalar_one()

            site_rows = session.exec(
                select(LibraryItemRecord.site, func.count())
                .group_by(LibraryItemRecord.site)
                .order_by(LibraryItemRecord.site)
            ).all()
            site_counts: dict[str, int] = {}
            for site, count in site_rows:
                key = site or "unknown"
                site_counts[key] = count

            type_rows = session.exec(
                select(LibraryItemRecord.item_type, func.count())
                .group_by(LibraryItemRecord.item_type)
                .order_by(LibraryItemRecord.item_type)
            ).all()
            type_counts: dict[str, int] = {}
            for item_type, count in type_rows:
                if item_type:
                    type_counts[item_type] = count

            tmdb_enriched = session.exec(
                select(func.count()).select_from(LibraryItemRecord).where(
                    LibraryItemRecord.tmdb_id.is_not(None)
                )
            ).scalar_one()

        tmdb_missing = max(total - tmdb_enriched, 0)

        return LibraryMetricsModel(
            total=total,
            site_counts=site_counts,
            type_counts=type_counts,
            tmdb_enriched=tmdb_enriched,
            tmdb_missing=tmdb_missing,
        )


def _to_model(record: LibraryItemRecord) -> LibraryItemModel:
    """Convert a library record into a response model."""

    variants = []
    if record.variants:
        for variant in record.variants:
            if variant and isinstance(variant, dict):
                try:
                    variants.append(StreamVariantModel.model_validate(variant))
                except Exception:
                    # Skip invalid variants
                    pass
    
    return LibraryItemModel(
        id=record.id,
        title=record.title,
        item_type=record.item_type,
        site=record.site,
        url=record.url,
        year=record.year,
        tmdb_id=record.tmdb_id,
        variants=variants,
    )
