"""Library endpoints for querying resolver catalog metadata."""
from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_library_store
from ..schemas import LibraryItemModel, LibraryListModel
from ..stores.library_store import LibraryStore

router = APIRouter(prefix="/library", tags=["library"])


@router.get("", response_model=LibraryListModel)
def list_library_items(
    query: str | None = Query(default=None, description="Optional title search term."),
    page: int = Query(default=1, ge=1, description="Page number starting at 1."),
    page_size: int = Query(
        default=25,
        ge=1,
        le=100,
        description="Number of items to return per page.",
    ),
    store: LibraryStore = Depends(get_library_store),
) -> LibraryListModel:
    """Return paginated library items matching the optional query."""

    return store.list(query=query, page=page, page_size=page_size)


@router.get("/{item_id}", response_model=LibraryItemModel)
def get_library_item(item_id: str, store: LibraryStore = Depends(get_library_store)) -> LibraryItemModel:
    """Return details for a single library item, raising when missing."""

    item = store.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Library item not found")
    return item
