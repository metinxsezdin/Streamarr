"""Library store exposing read access to persisted catalog items."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlmodel import Session

from ..models import LibraryItemRecord
from ..schemas import (
    LibraryItemModel,
    LibraryListModel,
    LibraryMetricsModel,
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
        site: str | None,
        item_type: str | None,
        year: int | None,
        year_min: int | None,
        year_max: int | None,
        has_tmdb: bool | None,
        page: int,
        page_size: int,
    ) -> LibraryListModel:
        """Return a paginated set of library items matching the provided filters."""

        offset = (page - 1) * page_size
        filters = []
        if query:
            filters.append(func.lower(LibraryItemRecord.title).like(f"%{query.lower()}%"))
        if site:
            filters.append(func.lower(LibraryItemRecord.site) == site.lower())
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
        items_statement = select(LibraryItemRecord).order_by(LibraryItemRecord.updated_at.desc())
        for condition in filters:
            count_statement = count_statement.where(condition)
            items_statement = items_statement.where(condition)

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

    variants = [StreamVariantModel.model_validate(variant) for variant in record.variants or []]
    return LibraryItemModel(
        id=record.id,
        title=record.title,
        item_type=record.item_type,
        site=record.site,
        year=record.year,
        tmdb_id=record.tmdb_id,
        variants=variants,
    )
