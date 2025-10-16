"""Configuration endpoints."""
from fastapi import APIRouter, Depends

from ..dependencies import get_config_store
from ..schemas import ConfigModel, ConfigUpdate
from ..stores.config_store import ConfigStore

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigModel)
def read_config(store: ConfigStore = Depends(get_config_store)) -> ConfigModel:
    """Return the current configuration."""
    return store.read()


@router.put("", response_model=ConfigModel)
def update_config(
    update: ConfigUpdate, store: ConfigStore = Depends(get_config_store)
) -> ConfigModel:
    """Update and return the configuration."""
    return store.update(update)
