"""Output contract for Step 0-C (Forward Model)."""
from dataclasses import dataclass
import mne


@dataclass(frozen=True)
class ForwardModelOutput:
    """Step 0-C output DTO.

    Attributes:
        forward: Computed Forward solution (Lead Field matrix).
        trans: Coordinate transformation matrix from head to MRI.
        info: Measurement info containing electrode positions and montage.
        fwd_file_path: Path to saved forward solution file (*-fwd.fif).
    """
    forward: mne.Forward
    trans: mne.transforms.Transform
    info: mne.Info
    fwd_file_path: str = ""
