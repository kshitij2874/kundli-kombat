import asyncio
from typing import Any

import httpx

from .config import get_settings


class ConvexUnavailable(RuntimeError):
    pass


async def mutation(path: str, args: dict[str, Any]) -> Any:
    return await _call("mutation", path, args)


async def query(path: str, args: dict[str, Any]) -> Any:
    return await _call("query", path, args)


async def _call(function_type: str, path: str, args: dict[str, Any]) -> Any:
    settings = get_settings()
    if settings.convex_url is None:
        raise ConvexUnavailable("CONVEX_URL is not configured")
    url = f"{str(settings.convex_url).rstrip('/')}/api/{function_type}"
    headers = {"Content-Type": "application/json"}
    timeout = httpx.Timeout(20, connect=10)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(2):
            try:
                response = await client.post(
                    url,
                    headers=headers,
                    json={"path": path, "args": args, "format": "json"},
                )
                response.raise_for_status()
                payload = response.json()
                break
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == 1:
                    raise ConvexUnavailable("Convex request failed after retry") from exc
                await asyncio.sleep(0.35)
    if payload.get("status") != "success":
        raise ConvexUnavailable(payload.get("errorMessage", f"Convex {function_type} failed"))
    return payload.get("value")
