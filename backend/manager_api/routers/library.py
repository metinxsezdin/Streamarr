"""Library endpoints for querying resolver catalog metadata."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_library_store
from ..schemas import (
    LibraryItemModel,
    LibraryListModel,
    LibraryMetricsModel,
    LibrarySortOption,
)
from ..stores.library_store import LibraryStore

router = APIRouter(prefix="/library", tags=["library"])


@router.get("", response_model=LibraryListModel)
def list_library_items(
    query: str | None = Query(default=None, description="Optional title search term."),
    sites: Annotated[
        list[str] | None,
        Query(
            alias="site",
            description=(
                "Filter results to one or more source sites. "
                "Repeat the query parameter to include multiple sites."
            ),
        ),
    ] = None,
    item_type: str | None = Query(
        default=None,
        description="Filter results by item type (movie or episode).",
    ),
    year: int | None = Query(
        default=None,
        ge=1800,
        le=3000,
        description="Filter results by an exact release year.",
    ),
    year_min: int | None = Query(
        default=None,
        ge=1800,
        le=3000,
        description="Filter results to items released on or after this year.",
    ),
    year_max: int | None = Query(
        default=None,
        ge=1800,
        le=3000,
        description="Filter results to items released on or before this year.",
    ),
    has_tmdb: bool | None = Query(
        default=None,
        description="Filter by presence of TMDB metadata (true for only enriched items, false for missing).",
    ),
    sort: LibrarySortOption = Query(
        default="updated_desc",
        description="Sort ordering applied to the returned items.",
    ),
    page: int = Query(default=1, ge=1, description="Page number starting at 1."),
    page_size: int = Query(
        default=25,
        ge=1,
        le=100,
        description="Number of items to return per page.",
    ),
    store: LibraryStore = Depends(get_library_store),
) -> LibraryListModel:
    """Return paginated library items matching the provided filters."""

    return store.list(
        query=query,
        sites=sites,
        item_type=item_type,
        year=year,
        year_min=year_min,
        year_max=year_max,
        has_tmdb=has_tmdb,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/metrics", response_model=LibraryMetricsModel)
def library_metrics(store: LibraryStore = Depends(get_library_store)) -> LibraryMetricsModel:
    """Return aggregate catalog statistics for dashboards."""

    return store.metrics()


@router.get("/{item_id}", response_model=LibraryItemModel)
def get_library_item(item_id: str, store: LibraryStore = Depends(get_library_store)) -> LibraryItemModel:
    """Return details for a single library item, raising when missing."""

    item = store.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Library item not found")
    return item
