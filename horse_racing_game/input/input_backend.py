from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PhysicalInput:
    code: str


class InputBackend(ABC):
    @abstractmethod
    def poll(self) -> tuple[PhysicalInput, ...]:
        """Return inputs observed since the previous poll."""