"""Parsl configurations for Colmena."""
from __future__ import annotations

from parsl import HighThroughputExecutor
from parsl.addresses import address_by_hostname
from parsl.channels import LocalChannel
from parsl.config import Config
from parsl.executors.base import ParslExecutor
from parsl.providers import LocalProvider


def get_config(output_dir: str, workers: int = 1) -> Config:
    """Create local executor Parsl config."""
    executors: list[ParslExecutor] = [
        HighThroughputExecutor(
            label='htex-local',
            max_workers=workers,
            address=address_by_hostname(),
            cores_per_worker=1,
            provider=LocalProvider(
                channel=LocalChannel(),
                init_blocks=1,
                max_blocks=1,
            ),
        ),
    ]

    return Config(executors=executors, run_dir=output_dir)
