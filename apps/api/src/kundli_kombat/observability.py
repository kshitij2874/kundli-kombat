from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from uuid import uuid4

from langfuse import Langfuse, propagate_attributes

from .config import get_settings


@dataclass
class TraceResult:
    trace_id: str
    started_at: float
    exported: bool

    @property
    def latency_ms(self) -> int:
        return round((perf_counter() - self.started_at) * 1000)


@lru_cache
def get_langfuse() -> Langfuse:
    settings = get_settings()
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=str(settings.langfuse_host) if settings.langfuse_host else None,
        environment=settings.app_env,
        release="kundli-kombat-0.1.0",
    )


@lru_cache
def langfuse_authenticated() -> bool:
    if not get_settings().langfuse_configured:
        return False
    try:
        return get_langfuse().auth_check()
    except Exception:
        return False


@contextmanager
def traced_task(name: str, task: str, player_id: str = "system") -> Iterator[TraceResult]:
    settings = get_settings()
    started_at = perf_counter()
    if not settings.langfuse_configured or not langfuse_authenticated():
        yield TraceResult(trace_id=f"local-{uuid4().hex}", started_at=started_at, exported=False)
        return

    langfuse = get_langfuse()
    with langfuse.start_as_current_observation(as_type="span", name=name) as span:
        with propagate_attributes(
            trace_name=f"kundli-kombat.{task}",
            user_id=player_id,
            tags=["agent:desk-manager", f"task:{task}", f"player:{player_id}"],
            metadata={"app": "kundli-kombat", "environment": settings.app_env},
        ):
            result = TraceResult(
                trace_id=langfuse.get_current_trace_id() or span.trace_id,
                started_at=started_at,
                exported=True,
            )
            try:
                yield result
                span.update(output={"ok": True, "latencyMs": result.latency_ms})
            except Exception as exc:
                span.update(level="ERROR", status_message=str(exc), output={"ok": False})
                raise


def flush_traces() -> None:
    if langfuse_authenticated():
        get_langfuse().flush()


@contextmanager
def agent_step(name: str, metadata: dict[str, object] | None = None) -> Iterator[None]:
    if not langfuse_authenticated():
        yield
        return
    langfuse = get_langfuse()
    with langfuse.start_as_current_observation(
        as_type="span", name=name, metadata=metadata or {},
    ) as span:
        try:
            yield
            span.update(output={"ok": True})
        except Exception as exc:
            span.update(level="ERROR", status_message=str(exc), output={"ok": False})
            raise
