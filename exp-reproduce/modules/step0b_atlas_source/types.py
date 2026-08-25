"""Configuration and internal types for Step 0-B (Atlas & Source Space)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class AtlasSourceConfig:
    """Step 0-B configuration parameters.

    Attributes:
        cerebra_nii_path: Path to CerebrA atlas NIfTI image (.nii or .nii.gz).
        cerebra_csv_path: Path to CerebrA label details table (.csv).
        spacing: Source space grid density / spacing (default: 'oct6').
        surface: Cortical surface for grid placement (default: 'white').
        overwrite: Overwrite existing files (default: False).
    """
    cerebra_nii_path: str
    cerebra_csv_path: str
    spacing: str = "oct6"
    surface: str = "white"
    overwrite: bool = False
