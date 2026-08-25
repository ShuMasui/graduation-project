"""Configuration and internal types for Step 0-C (Forward Model)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ForwardModelConfig:
    """Step 0-C configuration parameters.

    Attributes:
        montage_name: Standard EEG montage name (default: 'GSN-HydroCel-128').
        eeg_channels_count: Number of EEG channels to use (default: 128).
        mindist: Minimum distance of sources from inner skull in mm (default: 5.0).
        n_jobs: Number of parallel jobs for forward computation (default: 1).
        overwrite: Overwrite existing files (default: False).
    """
    montage_name: str = "GSN-HydroCel-128"
    eeg_channels_count: int = 128
    mindist: float = 5.0
    n_jobs: int = 1
    overwrite: bool = False
