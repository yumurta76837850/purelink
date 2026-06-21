"""
tests/test_logger.py — logger modülü için unit testler
"""

import pytest
import time
import threading
import io
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sentinel_core.logger import (
    SentinelLogger,
    PerformanceTracker,
    get_logger,
    time_execution,
    Level,
)


# ──────────────────────────────────────────────
# SentinelLogger
# ──────────────────────────────────────────────

class TestSentinelLogger:
    def setup_method(self):
        self.buf = io.StringIO()
        self.log = SentinelLogger("test", level=Level.DEBUG, output=self.buf, color=False)

    def test_info_logged(self):
        self.log.info("merhaba")
        assert "merhaba" in self.buf.getvalue()

    def test_level_name_in_output(self):
        self.log.warning("uyarı")
        assert "WARNING" in self.buf.getvalue()

    def test_logger_name_in_output(self):
        self.log.info("mesaj")
        assert "[test]" in self.buf.getvalue()

    def test_extra_fields(self):
        self.log.info("bağlandı", extra={"port": 9000, "host": "localhost"})
        out = self.buf.getvalue()
        assert "port=9000" in out
        assert "host=localhost" in out

    def test_level_filtering(self):
        log = SentinelLogger("filter", level=Level.ERROR, output=self.buf, color=False)
        log.debug("bu görünmemeli")
        log.info("bu da görünmemeli")
        log.error("bu görünmeli")
        out = self.buf.getvalue()
        assert "bu görünmemeli" not in out
        assert "bu görünmeli" in out

    def test_all_levels(self):
        self.log.debug("d")
        self.log.info("i")
        self.log.warning("w")
        self.log.error("e")
        self.log.critical("c")
        out = self.buf.getvalue()
        for msg in ["d", "i", "w", "e", "c"]:
            assert msg in out

    def test_thread_safe(self):
        errors = []

        def worker():
            try:
                for i in range(50):
                    self.log.info(f"thread mesajı {i}")
            except Exception as ex:
                errors.append(ex)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread hatası: {errors}"

    def test_get_logger_returns_instance(self):
        log = get_logger("myapp")
        assert isinstance(log, SentinelLogger)
        assert log.name == "myapp"


# ──────────────────────────────────────────────
# @time_execution
# ──────────────────────────────────────────────

class TestTimeExecution:
    def setup_method(self):
        self.buf = io.StringIO()
        self.log = SentinelLogger("perf", level=Level.DEBUG, output=self.buf, color=False)

    def test_sync_function_runs(self):
        @time_execution(logger=self.log)
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_sync_logs_duration(self):
        @time_execution(logger=self.log)
        def noop():
            pass

        noop()
        assert "µs" in self.buf.getvalue()

    def test_async_function_runs(self):
        import asyncio

        @time_execution(logger=self.log)
        async def async_add(a, b):
            return a + b

        result = asyncio.run(async_add(3, 4))
        assert result == 7

    def test_async_logs_duration(self):
        import asyncio

        @time_execution(logger=self.log)
        async def async_noop():
            await asyncio.sleep(0)

        asyncio.run(async_noop())
        assert "µs" in self.buf.getvalue()

    def test_custom_label(self):
        @time_execution(logger=self.log, label="özel_etiket")
        def fn():
            pass

        fn()
        assert "özel_etiket" in self.buf.getvalue()

    def test_preserves_function_name(self):
        @time_execution(logger=self.log)
        def my_special_func():
            pass

        assert my_special_func.__name__ == "my_special_func"

    def test_exception_propagates(self):
        @time_execution(logger=self.log)
        def broken():
            raise ValueError("test hatası")

        with pytest.raises(ValueError, match="test hatası"):
            broken()


# ──────────────────────────────────────────────
# PerformanceTracker
# ──────────────────────────────────────────────

class TestPerformanceTracker:
    def test_empty_stats(self):
        tracker = PerformanceTracker("test")
        stats   = tracker.stats()
        assert stats["count"] == 0

    def test_single_measurement(self):
        tracker = PerformanceTracker("test")
        with tracker.measure():
            time.sleep(0.001)
        stats = tracker.stats()
        assert stats["count"]   == 1
        assert stats["min_µs"]  > 0
        assert stats["max_µs"]  >= stats["min_µs"]
        assert stats["avg_µs"]  > 0

    def test_multiple_measurements(self):
        tracker = PerformanceTracker("multi")
        for _ in range(10):
            with tracker.measure():
                pass
        stats = tracker.stats()
        assert stats["count"]  == 10
        assert stats["min_µs"] <= stats["avg_µs"] <= stats["max_µs"]

    def test_reset(self):
        tracker = PerformanceTracker("reset_test")
        with tracker.measure():
            pass
        tracker.reset()
        assert tracker.stats()["count"] == 0

    def test_thread_safe(self):
        tracker = PerformanceTracker("threads")
        errors  = []

        def worker():
            try:
                for _ in range(100):
                    with tracker.measure():
                        pass
            except Exception as ex:
                errors.append(ex)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert tracker.stats()["count"] == 500

    def test_total_ms(self):
        tracker = PerformanceTracker("total")
        for _ in range(3):
            with tracker.measure():
                time.sleep(0.001)
        assert tracker.stats()["total_ms"] >= 3.0
