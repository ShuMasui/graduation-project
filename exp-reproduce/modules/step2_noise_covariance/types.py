"""Internal types and configuration for Step 2 noise covariance."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NoiseCovConfig:
    """Configuration parameters for noise covariance calculation."""

    tmin: float = 0.0
    tmax: Optional[float] = None
    method: str = "empirical"
