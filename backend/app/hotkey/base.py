from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

ToggleCallback = Callable[[], None]


class HotkeyTrigger(ABC):
    """Notifies the pipeline orchestrator to toggle recording on/off."""

    @abstractmethod
    def start(self, on_toggle: ToggleCallback) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...
