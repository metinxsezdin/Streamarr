"""Library store exposing read access to persisted catalog items."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlmodel import Session

from ..models import LibraryItemRecord
from ..schemas import LibraryItemModel, LibraryListModel, StreamVariantModel


@dataclass(slots=True)
class LibraryStore:
    """Read-oriented accessor for manager library items."""

    engine: Engine

    def list(
        self,
        *,
        query: str | None,
        page: int,
        page_size: int,
    ) -> LibraryListModel:
        """Return a paginated set of library items matching the optional query."""

        offset = (page - 1) * page_size
        filters = []
        if query:
            filters.append(func.lower(LibraryItemRecord.title).like(f"%{query.lower()}%"))

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
