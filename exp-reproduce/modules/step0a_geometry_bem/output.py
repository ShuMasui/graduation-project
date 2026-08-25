"""Output contract for Step 0-A (Geometry & BEM)."""
from dataclasses import dataclass
import mne


@dataclass(frozen=True)
class GeometryBEMOutput:
    """Step 0-A output DTO.

    Attributes:
        subjects_dir: FreeSurfer base directory.
        subject_name: Subject identifier ('icbm152').
        bem_surfaces_path: Path to BEM surfaces file (*-bem.fif).
        bem_solution: 3-layer BEM conductor model.
    """
    subjects_dir: str
    subject_name: str
    bem_surfaces_path: str
    bem_solution: mne.bem.ConductorModel
