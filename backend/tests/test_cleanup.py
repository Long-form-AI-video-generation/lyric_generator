from __future__ import annotations

import asyncio

import pytest

from backend.services.cleanup import run_periodic_cleanup


@pytest.mark.asyncio
async def test_periodic_cleanup_runs_until_cancelled() -> None:
    calls = 0

    def cleanup() -> int:
        nonlocal calls
        calls += 1
        return 0

    task = asyncio.create_task(
        run_periodic_cleanup(cleanup, interval_seconds=0)
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert calls >= 1


@pytest.mark.asyncio
async def test_periodic_cleanup_survives_cleanup_errors() -> None:
    calls = 0

    def cleanup() -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        return 0

    task = asyncio.create_task(
        run_periodic_cleanup(cleanup, interval_seconds=0)
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert calls >= 2

