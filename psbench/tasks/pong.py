from __future__ import annotations

from typing import NamedTuple


class ProxyStats(NamedTuple):
    """Proxy stats from within task."""

    input_get_ms: float | None = None
    input_resolve_ms: float | None = None
    output_set_ms: float | None = None
    output_proxy_ms: float | None = None


def pong(data: bytes, *, result_size: int = 0, sleep: float = 0) -> bytes:
    """Task that takes data and returns more data.

    Args:
        data (bytes): input data.
        result_size (int): size of results byte array (default: 0).
        sleep (float): seconds to sleep for to simulate work (default: 0).

    Returns:
        bytes
    """
    import time

    from psbench.utils import randbytes

    assert isinstance(data, bytes)
    time.sleep(sleep)

    return randbytes(result_size)


def pong_proxy(
    data: bytes,
    *,
    evict_result: bool = True,
    result_size: int = 0,
    sleep: float = 0,
) -> tuple[bytes, ProxyStats | None]:
    """Task that takes a proxy of data and return a proxy of data.

    Args:
        data (bytes): input data.
        evict_result (bool): Set evict flag in returned proxy (default: True).
        result_size (int): size of results byte array.
        sleep (float): seconds to sleep for to simulate work (default: 0). If
            the sleep is non-zero, the input proxy will be asynchronously
            resolved during the sleep.

    Returns:
        Tuple of bytes and ProxyStats is stat tracking on the store is enabled.

    Raises:
        UnknownStoreError:
            if the ProxyStore backend cannot be extracted from the input
            Proxy.
    """
    import time

    from proxystore.proxy import Proxy
    from proxystore.proxy import is_resolved
    from proxystore.store.utils import resolve_async
    from proxystore.store import get_store
    from proxystore.store import UnknownStoreError

    from psbench.utils import randbytes

    assert isinstance(data, Proxy)
    assert not is_resolved(data)

    if sleep > 0.0:
        resolve_async(data)
        time.sleep(sleep)

    assert isinstance(data, bytes) and isinstance(data, Proxy)

    result_data = randbytes(result_size)
    store = get_store(data)
    if store is None:  # pragma: no cover
        # init_store does not return None in ProxyStore <= 0.3.3
        raise UnknownStoreError('Cannot find ProxyStore backend to use.')
    result: Proxy[bytes] = store.proxy(result_data, evict=evict_result)

    stats: ProxyStats | None = None
    if store.has_stats:
        stats = ProxyStats(
            input_get_ms=store.stats(data)['get'].avg_time_ms,
            input_resolve_ms=store.stats(data)['resolve'].avg_time_ms,
            output_set_ms=store.stats(result)['set'].avg_time_ms,
            output_proxy_ms=store.stats(result)['proxy'].avg_time_ms,
        )

    return (result, stats)
