"""Internal types and configuration for Step 3 source localization."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SourceLocConfig:
    """Configuration parameters for eLORETA source localization."""

    method: str = "eLORETA"
    loose: float = 0.2
    depth: float = 0.8
    pick_ori: Optional[str] = None
    prepared: bool = False
