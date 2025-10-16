"""Resolver proxy endpoints for the Manager API."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_config_store, get_resolver_service
from ..schemas import ConfigModel, ResolverProcessStatusModel
from ..services import (
    ResolverAlreadyRunningError,
    ResolverNotRunningError,
    ResolverService,
    ResolverServiceError,
)
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


@router.post(
    "/start",
    summary="Launch managed resolver process",
    response_model=ResolverProcessStatusModel,
)
def resolver_start(
    config_store: ConfigStore = Depends(get_config_store),
    resolver_service: ResolverService = Depends(get_resolver_service),
) -> ResolverProcessStatusModel:
    """Start the resolver process managed by the API service."""

    config: ConfigModel = config_store.read()

    try:
        status = resolver_service.start_process(resolver_url=config.resolver_url)
    except ResolverAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ResolverServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ResolverProcessStatusModel.model_validate(asdict(status))


@router.post(
    "/stop",
    summary="Stop managed resolver process",
    response_model=ResolverProcessStatusModel,
)
def resolver_stop(
    resolver_service: ResolverService = Depends(get_resolver_service),
) -> ResolverProcessStatusModel:
    """Stop the resolver process if it is running."""

    try:
        status = resolver_service.stop_process()
    except ResolverNotRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ResolverServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ResolverProcessStatusModel.model_validate(asdict(status))


@router.get(
    "/status",
    summary="Managed resolver process status",
    response_model=ResolverProcessStatusModel,
)
def resolver_status(
    resolver_service: ResolverService = Depends(get_resolver_service),
) -> ResolverProcessStatusModel:
    """Return the status of the resolver process managed by the API."""

    status = resolver_service.process_status()
    return ResolverProcessStatusModel.model_validate(asdict(status))
