"""Configuration endpoints."""
from fastapi import APIRouter, Depends

from ..dependencies import get_config_store, get_settings
from ..schemas import ConfigModel, ConfigUpdate
from ..settings import ManagerSettings
from ..utils.paths import ensure_strm_directory
from ..stores.config_store import ConfigStore

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigModel)
def read_config(store: ConfigStore = Depends(get_config_store)) -> ConfigModel:
    """Return the current configuration."""
    return store.read()


@router.put("", response_model=ConfigModel)
def update_config(
    update: ConfigUpdate,
    store: ConfigStore = Depends(get_config_store),
    settings: ManagerSettings = Depends(get_settings),
) -> ConfigModel:
    """Update and return the configuration."""

    payload = update.model_copy()
    if payload.strm_output_path is not None:
        trimmed = payload.strm_output_path.strip()
        if not trimmed:
            trimmed = settings.default_strm_output_path
        payload.strm_output_path = ensure_strm_directory(trimmed)

    return store.update(payload)
