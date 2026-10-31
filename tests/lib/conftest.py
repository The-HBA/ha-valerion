"""Fixtures for the protocol library tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from .fake_projector import DEFAULT_VALUES, FakeProjector


@pytest.fixture
async def projector() -> AsyncIterator[FakeProjector]:
    """A running fake projector without security code."""
    fake = FakeProjector(values=dict(DEFAULT_VALUES))
    await fake.start()
    yield fake
    await fake.stop()


@pytest.fixture
async def secured_projector() -> AsyncIterator[FakeProjector]:
    """A running fake projector that requires the code ``1234``."""
    fake = FakeProjector(security_code="1234", values=dict(DEFAULT_VALUES))
    await fake.start()
    yield fake
    await fake.stop()
