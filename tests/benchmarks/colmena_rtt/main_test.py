from __future__ import annotations

from typing import Generator

import pytest
import redis

from psbench.benchmarks.colmena_rtt.main import main

REDIS_HOST = 'localhost'
REDIS_PORT = 6379
try:
    redis_client = redis.StrictRedis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
    )
    redis_client.ping()
    redis_available = True
except redis.exceptions.ConnectionError:
    redis_available = False


@pytest.fixture
def default_args(tmp_path) -> Generator[list[str], None, None]:
    run_dir = tmp_path / 'runs'
    run_dir.mkdir()
    args = [
        '--output-dir',
        str(run_dir),
        '--redis-host',
        REDIS_HOST,
        '--redis-port',
        str(REDIS_PORT),
    ]
    yield args


@pytest.mark.parametrize(
    'args',
    (
        # base, no proxystore
        [
            '--input-sizes',
            '100',
            '1000',
            '--output-sizes',
            '100',
            '1000',
            '--task-repeat',
            '2',
        ],
        # TODO: handle special cases of params
    ),
)
@pytest.mark.skipif(
    not redis_available,
    reason='Unable to connect to Redis server at localhost:6379',
)
def test_parsl_e2e(args: list[str], default_args: list[str]) -> None:
    args = ['--parsl'] + args + default_args
    assert main(args) == 0


@pytest.mark.skipif(
    not redis_available,
    reason='Unable to connect to Redis server at localhost:6379',
)
def test_mocked_funcx(default_args: list[str]) -> None:
    # TODO: funcx example with mock funcx executor
    pass
