"""Colmena round trip task time benchmark.

Tests round trip task times in Colmena with configurable backends,
ProxyStore methods, payload sizes, etc. Colmena additionally requires
Redis which is not installed when installing the psbench package.

The Parsl executor config can be modified in
    psbench/benchmarks/colmena_rtt/config.py

Note: this is a fork of
    https://github.com/exalearn/colmena/tree/master/demo_apps/synthetic-data
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from threading import Event
from typing import Sequence

import numpy
import proxystore.proxy
from colmena.models import Result
from colmena.redis.queue import ClientQueues
from colmena.redis.queue import make_queue_pairs
from colmena.task_server import ParslTaskServer
from colmena.task_server.base import BaseTaskServer
from colmena.task_server.funcx import FuncXTaskServer
from colmena.thinker import agent
from colmena.thinker import BaseThinker
from funcx import FuncXClient
from proxystore.store.base import Store
from proxystore.store.utils import get_key

from psbench.argparse import add_logging_options
from psbench.argparse import add_proxystore_options
from psbench.benchmarks.colmena_rtt.config import get_config
from psbench.logging import init_logging
from psbench.logging import TESTING_LOG_LEVEL
from psbench.proxystore import init_store_from_args


logger = logging.getLogger('colmena-rtt')


class Thinker(BaseThinker):
    """Benchmark Thinker.

    Executes matrix of tasks based on parameters synchronously (i.e., one
    task is executes and completes before the next one is created).
    """

    def __init__(
        self,
        queue: ClientQueues,
        store: Store | None,
        input_sizes_bytes: list[int],
        output_sizes_bytes: list[int],
        task_repeat: int,
        task_sleep: float,
        reuse_inputs: bool,
    ) -> None:
        """Init Thinker."""
        super().__init__(queue)
        self.store = store
        self.input_sizes_bytes = input_sizes_bytes
        self.output_sizes_bytes = output_sizes_bytes
        self.task_repeat = task_repeat
        self.task_sleep = task_sleep
        self.reuse_inputs = reuse_inputs

        self.results: list[Result] = []
        self.alternator = Event()

    @agent
    def consumer(self) -> None:
        """Process and save task results."""
        expected_tasks = (
            self.task_repeat
            * len(self.input_sizes_bytes)
            * len(self.output_sizes_bytes)
        )
        for _ in range(expected_tasks):
            result = self.queues.get_result(topic='generate')
            value = result.value
            if (
                isinstance(value, proxystore.proxy.Proxy)
                and self.store is not None
            ):
                self.store.evict(get_key(value))

            result.inputs = '<removed>'
            result.value = '<removed>'
            logger.log(
                TESTING_LOG_LEVEL,
                'got result: {}'.format(str(result).replace('\n', ' ')),
            )
            self.results.append(result)
            self.alternator.set()

    @agent
    def producer(self) -> None:
        """Execute tasks as ready."""
        for input_size in self.input_sizes_bytes:
            if self.reuse_inputs:
                input_data = empty_array(input_size)
            for output_size in self.output_sizes_bytes:
                for _ in range(self.task_repeat):
                    if self.done.is_set():
                        break
                    if not self.reuse_inputs:
                        input_data = empty_array(input_size)
                    self.queues.send_inputs(
                        input_data,
                        output_size,
                        self.task_sleep,
                        method='target_function',
                        topic='generate',
                        task_info={
                            'input_size': input_size,
                            'output_size': output_size,
                        },
                    )
                    self.alternator.wait()
                    self.alternator.clear()


def empty_array(size: int) -> numpy.ndarray:
    """Create empty numpy array of size bytes."""
    return numpy.empty(int(size / 4), dtype=numpy.float32)


def target_function(
    data: numpy.ndarray,
    output_size_bytes: int,
    sleep: float = 0,
) -> numpy.ndarray:
    """Colmena target function.

    Args:
        data (ndarray): input data (may be a proxy).
        output_size_bytes (int): size of data to return.
        sleep (float): sleep (seconds) to simulate work.

    Returns:
        numpy array with size output_size_bytes.
    """
    import numpy
    import time
    import proxystore.proxy
    from proxystore.store import get_store
    from proxystore.store.utils import get_key

    # Check that proxy acts as the wrapped np object
    assert isinstance(data, numpy.ndarray)

    if isinstance(data, proxystore.proxy.Proxy):
        store = get_store(data)
        if store is not None:
            store.evict(get_key(data))

    time.sleep(sleep)  # simulate additional work

    return empty_array(output_size_bytes)


def main(argv: Sequence[str] | None = None) -> int:
    """Benchmark entrypoint."""
    argv = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(
        description='Template benchmark.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    backend_group = parser.add_mutually_exclusive_group(required=True)
    backend_group.add_argument(
        '--funcx',
        action='store_true',
        help='Use the FuncX Colmena Task Server',
    )
    backend_group.add_argument(
        '--parsl',
        action='store_true',
        help='Use the Parsl Colmena Task Server',
    )

    funcx_group = parser.add_argument_group()
    funcx_group.add_argument(
        '--endpoint',
        required='--funcx' in sys.argv,
        help='FuncX endpoint for task execution',
    )

    task_group = parser.add_argument_group()
    task_group.add_argument(
        '--redis-host',
        default='localhost',
        help='Redis server hostname',
    )
    task_group.add_argument(
        '--redis-port',
        default='6379',
        help='Redis server port',
    )
    task_group.add_argument(
        '--input-sizes',
        type=float,
        nargs='+',
        required=True,
        help='Task input sizes [bytes]',
    )
    task_group.add_argument(
        '--output-sizes',
        type=float,
        nargs='+',
        required=True,
        help='Task output sizes [bytes]',
    )
    task_group.add_argument(
        '--task-repeat',
        type=int,
        default=1,
        help='Number of time to repeat each task configuration',
    )
    task_group.add_argument(
        '--task-sleep',
        type=float,
        default=0,
        help='Sleep time for tasks',
    )
    task_group.add_argument(
        '--reuse-inputs',
        action='store_true',
        default=False,
        help='Send the same input to each task',
    )
    task_group.add_argument(
        '--output-dir',
        type=str,
        default='runs',
        help='Colmena run output directory',
    )

    add_logging_options(parser)
    add_proxystore_options(parser, required=False)
    args = parser.parse_args(argv)

    init_logging(args.log_file, args.log_level, force=True)
    store = init_store_from_args(args, stats=True)

    output_dir = os.path.join(
        args.output_dir,
        datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S'),
    )
    os.makedirs(output_dir, exist_ok=True)

    # Make the queues
    client_queues, server_queues = make_queue_pairs(
        args.redis_host,
        args.redis_port,
        topics=['generate'],
        serialization_method='pickle',
        keep_inputs=False,
        proxystore_name=None if store is None else store.name,
        proxystore_threshold=0,
    )

    doer: BaseTaskServer
    if args.funcx:
        fcx = FuncXClient()
        doer = FuncXTaskServer(
            {target_function: args.endpoint},
            fcx,
            server_queues,
        )
    elif args.parsl:
        config = get_config(output_dir)
        doer = ParslTaskServer([target_function], server_queues, config)

    thinker = Thinker(
        queue=client_queues,
        store=store,
        input_sizes_bytes=args.input_sizes,
        output_sizes_bytes=args.output_sizes,
        task_repeat=args.task_repeat,
        task_sleep=args.task_sleep,
        reuse_inputs=args.reuse_inputs,
    )

    try:
        # Launch the servers
        doer.start()
        thinker.start()
        logging.log(TESTING_LOG_LEVEL, 'launched thinker and task servers')

        # Wait for the task generator to complete
        thinker.join()
        logging.log(TESTING_LOG_LEVEL, 'thinker completed')
    finally:
        client_queues.send_kill_signal()

    # Wait for the task server to complete
    doer.join()
    logging.info(TESTING_LOG_LEVEL, 'task server completed')

    # TODO: add CSV logging
    # Write out results
    # filepath = os.path.join(out_dir, 'results.jsonl')
    # with open(filepath, 'w') as f:
    #    for result in thinker.results:
    #        f.write(f'{result.json()}\n')

    if store is not None:
        store.close()
        logger.log(TESTING_LOG_LEVEL, 'cleaned up {store.name}')

    return 0
