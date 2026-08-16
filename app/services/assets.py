"""Asset domain service."""

from app.enterprise import (
    create_asset,
    delete_asset,
    ensure_asset_for_target,
    get_asset,
    list_assets,
    update_asset,
)

__all__ = [
    "create_asset",
    "delete_asset",
    "ensure_asset_for_target",
    "get_asset",
    "list_assets",
    "update_asset",
]
