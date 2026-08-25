"""Output contract for Step 0-B (Atlas & Source Space)."""
from dataclasses import dataclass
from typing import List
import mne


@dataclass(frozen=True)
class AtlasSourceOutput:
    """Step 0-B output DTO.

    Attributes:
        src: Cortical source spaces (SourceSpaces).
        cerebra_labels: List of CerebrA cortical Label objects.
        total_sources: Total number of active source vertices.
        src_file_path: Path to saved src.fif file (optional).
    """
    src: mne.SourceSpaces
    cerebra_labels: List[mne.Label]
    total_sources: int
    src_file_path: str = ""
