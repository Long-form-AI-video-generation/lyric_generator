"""Periodic cleanup helpers for transient job files."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


async def run_periodic_cleanup(
    cleanup: Callable[[], int],
    *,
    interval_seconds: int,
) -> None:
    """Run cleanup forever until the task is cancelled."""

    while True:
        try:
            await asyncio.sleep(interval_seconds)
            removed = cleanup()
            if removed:
                logger.info("Cleaned up %d expired job director%s", removed, "y" if removed == 1 else "ies")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Periodic cleanup failed")

