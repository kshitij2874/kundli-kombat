from typing import Any

import httpx

from .config import get_settings


class ConvexUnavailable(RuntimeError):
    pass


async def mutation(path: str, args: dict[str, Any]) -> Any:
    settings = get_settings()
    if settings.convex_url is None:
        raise ConvexUnavailable("CONVEX_URL is not configured")
    url = f"{str(settings.convex_url).rstrip('/')}/api/mutation"
    headers = {"Content-Type": "application/json"}
    if settings.convex_deploy_key:
        headers["Authorization"] = f"Convex {settings.convex_deploy_key}"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            url,
            headers=headers,
            json={"path": path, "args": args, "format": "json"},
        )
        response.raise_for_status()
        payload = response.json()
    if payload.get("status") != "success":
        raise ConvexUnavailable(payload.get("errorMessage", "Convex mutation failed"))
    return payload.get("value")

