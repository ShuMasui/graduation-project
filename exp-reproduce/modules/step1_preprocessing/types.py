"""Internal types and configuration for Step 1 preprocessing."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PreprocessingConfig:
    """Configuration parameters for raw EEG preprocessing."""

    raw_eeg_path: str
    target_sampling_rate: float = 125.0
    l_freq: float = 1.0
    h_freq: float = 50.0
    apply_prep: bool = True
    ica_n_components: int = 20
    random_state: int = 42
