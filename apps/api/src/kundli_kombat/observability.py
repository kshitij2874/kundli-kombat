from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
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


@dataclass
class StepResult:
    cost_usd: float = 0.0


_current_task: ContextVar[str] = ContextVar("current_task", default="unknown")
_current_player: ContextVar[str] = ContextVar("current_player", default="system")


def _agent_name(step_name: str) -> str:
    return {
        "manager": "desk-manager",
        "interpreter": "interpreter",
        "referee": "match-referee",
        "sentinel": "safety-sentinel",
        "chart": "chart-specialist",
        "geocoder": "geocoder",
        "comms": "comms-specialist",
    }.get(step_name.split(".", 1)[0], step_name.split(".", 1)[0])


@lru_cache
def get_langfuse() -> Langfuse:
    settings = get_settings()
    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=str(settings.langfuse_endpoint) if settings.langfuse_endpoint else None,
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
    task_token = _current_task.set(task)
    player_token = _current_player.set(player_id)
    try:
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
    finally:
        _current_task.reset(task_token)
        _current_player.reset(player_token)


def flush_traces() -> None:
    if langfuse_authenticated():
        get_langfuse().flush()


@contextmanager
def agent_step(name: str, metadata: dict[str, object] | None = None) -> Iterator[StepResult]:
    result = StepResult()
    if not langfuse_authenticated():
        yield result
        return
    langfuse = get_langfuse()
    task = str((metadata or {}).get("task") or _current_task.get())
    player_id = _current_player.get()
    agent = _agent_name(name)
    with propagate_attributes(tags=[f"agent:{agent}", f"task:{task}", f"player:{player_id}"]):
        with langfuse.start_as_current_observation(
            as_type="span", name=name, metadata=metadata or {},
        ) as span:
            try:
                yield result
                span.update(output={"ok": True, "costUsd": result.cost_usd})
            except Exception as exc:
                span.update(
                    level="ERROR", status_message=str(exc),
                    output={"ok": False, "costUsd": result.cost_usd},
                )
                raise
