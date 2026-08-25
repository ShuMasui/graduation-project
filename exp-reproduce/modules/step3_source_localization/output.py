"""Output data contract for Step 3 source localization."""

from dataclasses import dataclass
import mne


@dataclass(frozen=True)
class SourceEstimateOutput:
    """Source localization estimate output DTO."""

    stc: mne.SourceEstimate
    method: str
    lambda2_used: float
