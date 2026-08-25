"""Configuration and internal types for Step 0-A (Geometry & BEM)."""
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class GeometryBEMConfig:
    """Step 0-A configuration parameters.

    Attributes:
        template_nii_path: Path to MNI-ICBM152 template image (.nii).
        subjects_dir: FreeSurfer subjects directory.
        subject_name: Subject identifier (default: 'icbm152').
        conductivity: Conductivities of brain, skull, scalp (default: (0.33, 0.0042, 0.33)).
        ico_resolution: Surface resolution (default: 4).
        overwrite: Overwrite existing files (default: False).
    """
    template_nii_path: str
    subjects_dir: str
    subject_name: str = "icbm152"
    conductivity: Tuple[float, float, float] = (0.33, 0.0042, 0.33)
    ico_resolution: int = 4
    overwrite: bool = False
