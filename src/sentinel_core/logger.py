"""
logger.py — Thread-safe loglama ve performans ölçüm motoru
"""

import sys
import time
import threading
import functools
from datetime import datetime
from enum import IntEnum
from typing import Callable, Optional


class Level(IntEnum):
    DEBUG    = 10
    INFO     = 20
    WARNING  = 30
    ERROR    = 40
    CRITICAL = 50


_COLORS = {
    Level.DEBUG:    "\033[36m",
    Level.INFO:     "\033[32m",
    Level.WARNING:  "\033[33m",
    Level.ERROR:    "\033[31m",
    Level.CRITICAL: "\033[35m",
}
_RESET = "\033[0m"
_BOLD  = "\033[1m"


class SentinelLogger:
    def __init__(
        self,
        name: str,
        level: Level = Level.INFO,
        output=sys.stdout,
        color: bool = True,
        show_thread: bool = False,
    ):
        self.name        = name
        self.level       = level
        self.output      = output
        self.color       = color
        self.show_thread = show_thread
        self._lock       = threading.Lock()

    def _format(self, level: Level, message: str, extra: Optional[dict] = None) -> str:
        ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        label = level.name.ljust(8)
        thread_part = f"[{threading.current_thread().name}] " if self.show_thread else ""

        if self.color:
            color = _COLORS.get(level, "")
            line  = f"{_BOLD}{ts}{_RESET} {color}{label}{_RESET} [{self.name}] {thread_part}{message}"
        else:
            line  = f"{ts} {label} [{self.name}] {thread_part}{message}"

        if extra:
            kv = " | ".join(f"{k}={v}" for k, v in extra.items())
            line += f"  » {kv}"
        return line

    def _emit(self, level: Level, message: str, extra: Optional[dict] = None) -> None:
        if level < self.level:
            return
        line = self._format(level, message, extra)
        with self._lock:
            print(line, file=self.output, flush=True)

    def debug   (self, msg: str, extra: Optional[dict] = None) -> None: self._emit(Level.DEBUG,    msg, extra)
    def info    (self, msg: str, extra: Optional[dict] = None) -> None: self._emit(Level.INFO,     msg, extra)
    def warning (self, msg: str, extra: Optional[dict] = None) -> None: self._emit(Level.WARNING,  msg, extra)
    def error   (self, msg: str, extra: Optional[dict] = None) -> None: self._emit(Level.ERROR,    msg, extra)
    def critical(self, msg: str, extra: Optional[dict] = None) -> None: self._emit(Level.CRITICAL, msg, extra)


_default_logger = SentinelLogger("sentinel", level=Level.DEBUG)


def get_logger(name: str, level: Level = Level.DEBUG) -> "SentinelLogger":
    return SentinelLogger(name, level=level)


def time_execution(
    logger: Optional["SentinelLogger"] = None,
    level: Level = Level.DEBUG,
    label: Optional[str] = None,
):
    def decorator(func: Callable) -> Callable:
        func_label = label or func.__qualname__

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start  = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_us = (time.perf_counter() - start) * 1_000_000
            _log = logger or _default_logger
            _log._emit(level, f"{func_label} tamamlandı", {"süre": f"{elapsed_us:.1f}µs"})
            return result

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start  = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed_us = (time.perf_counter() - start) * 1_000_000
            _log = logger or _default_logger
            _log._emit(level, f"{func_label} tamamlandı", {"süre": f"{elapsed_us:.1f}µs"})
            return result

        import inspect
        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator


class PerformanceTracker:
    def __init__(self, name: str):
        self.name    = name
        self._times: list[float] = []
        self._lock   = threading.Lock()

    class _Ctx:
        def __init__(self, tracker: "PerformanceTracker"):
            self._t     = tracker
            self._start = 0.0

        def __enter__(self) -> "PerformanceTracker._Ctx":
            self._start = time.perf_counter()
            return self

        def __exit__(self, *_) -> None:
            elapsed_us = (time.perf_counter() - self._start) * 1_000_000
            with self._t._lock:
                self._t._times.append(elapsed_us)

    def measure(self) -> "_Ctx":
        return self._Ctx(self)

    def stats(self) -> dict:
        with self._lock:
            if not self._times:
                return {"name": self.name, "count": 0}
            return {
                "name"    : self.name,
                "count"   : len(self._times),
                "min_µs"  : round(min(self._times), 2),
                "max_µs"  : round(max(self._times), 2),
                "avg_µs"  : round(sum(self._times) / len(self._times), 2),
                "total_ms": round(sum(self._times) / 1000, 3),
            }

    def reset(self) -> None:
        with self._lock:
            self._times.clear()
