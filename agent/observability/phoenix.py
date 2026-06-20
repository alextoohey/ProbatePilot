from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


def init_phoenix() -> None:
    """Placeholder for Phoenix/OpenInference initialization."""


@contextmanager
def span(name: str, **attributes: object) -> Iterator[None]:
    """No-op span with the same shape real tracing will keep using."""
    _ = (name, attributes)
    yield

