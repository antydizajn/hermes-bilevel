"""Process-local runtime singleton for observe mode."""
from __future__ import annotations

import threading
from typing import Any

from hermes_bilevel.config.schema import BilevelConfig, load_config
from hermes_bilevel.events.queue import BoundedEventQueue
from hermes_bilevel.hooks.handlers import HookHandlers
from hermes_bilevel.paths import get_bilevel_root
from hermes_bilevel.purity.registry import load_default_registry
from hermes_bilevel.storage.store import BilevelStore
from hermes_bilevel.version import __version__

_lock = threading.RLock()
_RUNTIME: "BilevelRuntime | None" = None


class BilevelRuntime:
    def __init__(self, cfg: BilevelConfig, store: BilevelStore) -> None:
        self.cfg = cfg
        self.store = store
        self.purity = load_default_registry(unknown_policy=str(cfg.get("purity", "unknown_policy", default="deny")))
        self.store.put_purity_registry(self.purity.registry_hash, self.purity.version, self.purity.to_dict())

        def writer(event: dict[str, Any]) -> None:
            self.store.insert_event(event)

        def on_drop(reason: str, data: dict[str, Any]) -> None:
            self.store.record_loss(reason, {"event_type": data.get("event_type")})

        self.queue = BoundedEventQueue(
            maxsize=int(cfg.get("hooks", "queue_size", default=2048)),
            overflow_policy=str(cfg.get("hooks", "overflow_policy", default="drop_newest")),
            on_drop=on_drop,
            writer=writer,
            start_worker=True,
        )
        self.handlers = HookHandlers(cfg, self.queue)
        self.plugin_version = __version__

    def close(self) -> None:
        self.queue.close()
        self.store.close()


def get_runtime(cfg: BilevelConfig | None = None, root: str | None = None) -> BilevelRuntime:
    global _RUNTIME
    with _lock:
        if _RUNTIME is None:
            cfg = cfg or load_config()
            store = BilevelStore(
                get_bilevel_root(cfg.get("storage", "root") or root),
                busy_timeout_ms=int(cfg.get("storage", "busy_timeout_ms", default=2500)),
                wal=bool(cfg.get("storage", "sqlite_wal", default=True)),
                max_blob_bytes=int(cfg.get("storage", "max_blob_bytes", default=10485760)),
            )
            _RUNTIME = BilevelRuntime(cfg, store)
        return _RUNTIME


def reset_runtime() -> None:
    global _RUNTIME
    with _lock:
        if _RUNTIME is not None:
            try:
                _RUNTIME.close()
            except Exception:
                pass
        _RUNTIME = None
