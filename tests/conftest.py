import logging
import signal
import sys
from collections.abc import Iterator

import pytest

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


@pytest.fixture(autouse=True)
def restore_signal_handlers() -> Iterator[None]:
    "Undo the SIGINT and SIGTERM handlers installed by verbose stores."
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    yield
    for sig, handler in handlers.items():
        signal.signal(sig, handler)


@pytest.fixture
def restore_courlan_level() -> Iterator[None]:
    "Undo the logger level set by cli.main()."
    logger = logging.getLogger("courlan")
    level = logger.level
    yield
    logger.setLevel(level)
