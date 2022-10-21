from __future__ import annotations

from psbench.benchmarks.template.main import main


def test_main() -> None:
    assert main([]) == 0
