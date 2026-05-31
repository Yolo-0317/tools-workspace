"""本地服务目录 API。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.services import registry

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("/catalog")
async def services_catalog() -> dict[str, Any]:
    catalog = await registry.build_catalog_async(with_health=True)
    return catalog


@router.get("/jellyfin")
async def jellyfin_mappings() -> dict[str, Any]:
    return await registry.load_jellyfin_mappings_async()


@router.get("/health-summary")
async def health_summary() -> dict[str, Any]:
    catalog = await registry.build_catalog_async(with_health=True)
    items: list[dict[str, Any]] = []
    for cat in catalog.get("categories", []):
        for item in cat.get("items", []):
            items.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "health": item.get("health"),
                    "docker_running": item.get("docker_running"),
                }
            )
    up = sum(1 for x in items if x.get("health", {}).get("status") == "up")
    return {"total": len(items), "up": up, "items": items}
