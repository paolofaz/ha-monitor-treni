"""Regression tests for validation and recovery of persisted delay watches."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
import voluptuous as vol

ROOT = Path(__file__).resolve().parents[1] / "custom_components/monitor_treni"

class DelayTests(unittest.TestCase):
    def test_service_schema_rejects_invalid_thresholds(self):
        source = ast.parse((ROOT / "__init__.py").read_text())
        node = next(n for n in source.body if isinstance(n, ast.Assign) and
                    any(isinstance(t, ast.Name) and t.id == "NOTIFY_ON_DELAY_SCHEMA" for t in n.targets))
        namespace = {"vol": vol, "cv": SimpleNamespace(string=str)}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "<schema>", "exec"), namespace)
        schema = namespace["NOTIFY_ON_DELAY_SCHEMA"]
        data = {"train_number": "123", "notify_target": "notify.test", "threshold_minutes": 1}
        self.assertEqual(schema(data)["threshold_minutes"], 1)
        for threshold in (0, -1):
            with self.assertRaises(vol.Invalid):
                schema(dict(data, threshold_minutes=threshold))
        with self.assertRaises(vol.Invalid):
            schema(dict(data, train_number="../bad"))

    def test_invalid_stored_thresholds_are_removed_before_evaluation(self):
        source = ast.parse((ROOT / "manager.py").read_text())
        cls = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == "MonitorTreniManager")
        node = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_load")
        import logging
        namespace = {"_LOGGER": logging.getLogger(__name__)}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "<load>", "exec"), namespace)
        async def run():
            checked, saved = [], []
            async def load():
                return {"watches": {"bad": {"threshold": 0}, "negative": {"threshold": -1}, "good": {"threshold": 5}}}
            async def save():
                saved.append(True)
            mgr = SimpleNamespace(store=SimpleNamespace(async_load=load), async_save=save,
                                  _check_delay_watch=checked.append, _sync_coordinator_watch=lambda key: None)
            await namespace["async_load"](mgr)
            self.assertEqual(checked, ["good"])
            self.assertEqual(list(mgr._delay_watches), ["good"])
            self.assertEqual(saved, [True])
        asyncio.run(run())
