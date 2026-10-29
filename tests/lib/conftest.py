"""Fixtures for the protocol library tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from .fake_projector import FakeProjector

DEFAULT_VALUES = {
    "%1POWR": "1",
    "%2INPT": "31",
    "%1AVMT": "20",
    "%3VOLM": "35",
    "%1INF1": "AWOL VISION",
    "%1INF2": "VisionMaster Pro2",
    "%1INFO": "Elgant Grey",
    "%1NAME": "Living room",
    "%2SVER": "V02.01.00E.Q0718 83 OEM01.0.0.0",
    "%3PICT": "HDR Theater",
    "%3PICL": "HDR Standard,HDR Vivid,HDR Theater",
    "%3LASL": "7",
}


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
