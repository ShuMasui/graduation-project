"""Configuration and internal types for Step 4 (CerebrA Parcellation)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SubjectMetadata:
    """Subject and trial metadata for parcellation.

    Attributes:
        subject_id: Identifier for the subject (e.g. 'sub-01').
        condition: Experimental condition (e.g. 'rest', 'video1', 'video2').
        duration_sec: Analysis duration window in seconds (default: 90.0).
        extract_mode: Label time course spatial extraction mode (default: 'mean').
    """
    subject_id: str
    condition: str
    duration_sec: float = 90.0
    extract_mode: str = "mean"
