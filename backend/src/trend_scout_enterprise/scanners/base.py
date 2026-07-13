"""Base scanner abstraction for all source types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class RawSignal:
    """A single collected signal from any source."""

    url: str
    title: str | None = None
    summary: str | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class BaseScanner(ABC):
    """Abstract base class for all signal scanners."""

    def __init__(self, source_id: str, config: dict[str, Any]) -> None:
        """Initialize scanner with source configuration.

        Args:
            source_id: UUID of the source being scanned.
            config: Source-specific configuration dict.
        """
        self.source_id = source_id
        self.config = config

    @abstractmethod
    async def scan(self) -> list[RawSignal]:
        """Fetch signals from the source.

        Returns:
            List of RawSignal objects.
        """
        ...

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the scanner's source type identifier."""
        ...
