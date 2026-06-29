from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.main import _build_tab_response_from_persistent_cache
from backend.app.llm_chart_compiler import spec_cache
from backend.app.schemas import TabRequest


class MainEndpointHelperTests(unittest.TestCase):
    def test_tab_response_returns_missing_error_without_backend_lazy_compile(self) -> None:
        def fake_build_tab_response(tab_num, request):
            raise ValueError("No compiled ChartSpecs found for tab_num: 1.1")

        missing_cache_path = Path(__file__).with_name("missing-chart-specs.json")
        self.assertFalse(missing_cache_path.exists())
        with (
            patch("backend.app.main.DEFAULT_SPEC_CACHE_PATH", missing_cache_path),
            patch("backend.app.main.build_tab_response", fake_build_tab_response),
            patch("backend.app.main.compile_grid") as compile_grid_mock,
        ):
            with self.assertRaisesRegex(ValueError, "No compiled ChartSpecs"):
                _build_tab_response_from_persistent_cache(
                    "1.1",
                    TabRequest(dropdown_state={}),
                )

        compile_grid_mock.assert_not_called()

    def test_tab_response_does_not_compile_for_other_value_errors(self) -> None:
        def fake_build_tab_response(tab_num, request):
            raise ValueError("Unknown tab_num: 9.9")

        with (
            patch("backend.app.main.build_tab_response", fake_build_tab_response),
            patch("backend.app.main.compile_grid") as compile_grid_mock,
        ):
            with self.assertRaisesRegex(ValueError, "Unknown tab_num"):
                _build_tab_response_from_persistent_cache(
                    "9.9",
                    TabRequest(dropdown_state={}),
                )

        compile_grid_mock.assert_not_called()

    def test_tab_response_clears_memory_cache_when_persistent_cache_is_missing(self) -> None:
        spec_cache.clear()
        spec_cache["stale-chart"] = {"hash": "old"}

        def fake_build_tab_response(tab_num, request):
            self.assertEqual(spec_cache, {})
            raise ValueError("Unknown tab_num: 9.9")

        missing_cache_path = Path(__file__).with_name("missing-chart-specs.json")
        self.assertFalse(missing_cache_path.exists())
        with (
            patch("backend.app.main.DEFAULT_SPEC_CACHE_PATH", missing_cache_path),
            patch("backend.app.main.build_tab_response", fake_build_tab_response),
            patch("backend.app.main.compile_grid") as compile_grid_mock,
        ):
            with self.assertRaisesRegex(ValueError, "Unknown tab_num"):
                _build_tab_response_from_persistent_cache(
                    "9.9",
                    TabRequest(dropdown_state={}),
                )

        compile_grid_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
