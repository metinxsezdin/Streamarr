"""Resolver proxy endpoints for the Manager API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_config_store, get_resolver_service
from ..schemas import ConfigModel
from ..services import ResolverService, ResolverServiceError
from ..stores.config_store import ConfigStore

router = APIRouter(prefix="/resolver", tags=["resolver"])


@router.get("/health", summary="Resolver status proxy")
def resolver_health(
    config_store: ConfigStore = Depends(get_config_store),
    resolver_service: ResolverService = Depends(get_resolver_service),
) -> dict[str, Any]:
    """Return the proxied resolver /health payload."""

    config: ConfigModel = config_store.read()

    try:
        return resolver_service.health(config.resolver_url)
    except ResolverServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
