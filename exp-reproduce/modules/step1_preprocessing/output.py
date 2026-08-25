"""Output data contract for Step 1 preprocessing."""

from dataclasses import dataclass
from typing import List
import mne


@dataclass(frozen=True)
class PreprocessedEEGOutput:
    """Preprocessed EEG output DTO."""

    raw: mne.io.BaseRaw
    sampling_rate: float
    bad_channels: List[str]
    removed_ica_components: List[int]
