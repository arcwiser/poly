from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import re
import hashlib


class Transformation(ABC):
    name: str = "base"
    version: str = "1.0.0"

    def __init__(self, seed: int, config: Optional[Dict[str, Any]] = None):
        self.seed = seed
        self.config = config or {}

    @abstractmethod
    def apply(self, ir: str) -> str:
        pass

    def _seeded_random(self, extra: str = "") -> int:
        data = f"{self.seed}:{self.name}:{extra}".encode()
        return int.from_bytes(
            hashlib.sha256(data).digest()[:4], "big"
        )

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "seed": self.seed,
            "config": self.config,
        }
