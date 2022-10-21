"""Benchmark template."""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Sequence

from psbench.argparse import add_logging_options
from psbench.logging import init_logging
from psbench.logging import TESTING_LOG_LEVEL

logger = logging.getLogger('template')


def run() -> None:
    """Benchmark logic."""
    logger.log(TESTING_LOG_LEVEL, 'starting template benchmark')

    # ...

    logger.log(TESTING_LOG_LEVEL, 'finished template benchmark')

    return None


def main(argv: Sequence[str] | None = None) -> int:
    """Benchmark entrypoint."""
    argv = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(
        description='Template benchmark.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Add arguments as necessary:
    # parser.add_argument('host', help='hostname')

    add_logging_options(parser)
    args = parser.parse_args(argv)

    init_logging(args.log_file, args.log_level, force=True)

    run()

    return 0
