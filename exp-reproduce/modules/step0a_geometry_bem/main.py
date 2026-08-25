"""Core logic for Step 0-A: Geometry reconstruction & 3-layer BEM extraction."""
import os
import mne

from .output import GeometryBEMOutput
from .types import GeometryBEMConfig


def run_geometry_bem(config: GeometryBEMConfig) -> GeometryBEMOutput:
    """Reconstruct head geometry and build 3-layer BEM conductor model from template MRI.

    Args:
        config: Configuration containing template MRI path, subjects directory,
            conductivity parameters, and mesh resolution.

    Returns:
        GeometryBEMOutput containing subject info, BEM surface paths, and
        the computed BEM conductor model solution.

    Raises:
        FileNotFoundError: If the template NIfTI image does not exist.
        ValueError: If conductivity or mesh resolution parameters are invalid.
    """
    # 1. Input validation
    if not os.path.exists(config.template_nii_path):
        raise FileNotFoundError(
            f"Template NIfTI file not found: {config.template_nii_path}"
        )

    if len(config.conductivity) != 3 or any(c <= 0 for c in config.conductivity):
        raise ValueError(
            f"Conductivity must be a 3-tuple of positive floats, got: {config.conductivity}"
        )

    if config.ico_resolution <= 0:
        raise ValueError(
            f"ico_resolution must be a positive integer, got: {config.ico_resolution}"
        )

    # 2. Environment and directory preparation
    os.environ["SUBJECTS_DIR"] = config.subjects_dir
    subject_bem_dir = os.path.join(config.subjects_dir, config.subject_name, "bem")
    os.makedirs(subject_bem_dir, exist_ok=True)

    bem_surfaces_path = os.path.join(
        subject_bem_dir, f"{config.subject_name}-5120-bem.fif"
    )
    bem_solution_path = os.path.join(
        subject_bem_dir, f"{config.subject_name}-5120-bem-sol.fif"
    )

    # 3. Cache verification
    if not config.overwrite and os.path.exists(bem_solution_path):
        bem_solution = mne.read_bem_solution(bem_solution_path)
        return GeometryBEMOutput(
            subjects_dir=config.subjects_dir,
            subject_name=config.subject_name,
            bem_surfaces_path=bem_surfaces_path,
            bem_solution=bem_solution,
        )

    # 4. BEM surface creation & solution calculation
    # Ensure watershed surfaces exist
    inner_skull_surf = os.path.join(subject_bem_dir, "inner_skull.surf")
    if not os.path.exists(inner_skull_surf) or config.overwrite:
        mne.bem.make_watershed_bem(
            subject=config.subject_name,
            subjects_dir=config.subjects_dir,
            overwrite=config.overwrite,
        )

    bem_surfaces = mne.make_bem_model(
        subject=config.subject_name,
        ico=config.ico_resolution,
        conductivity=list(config.conductivity),
        subjects_dir=config.subjects_dir,
    )
    bem_solution = mne.make_bem_solution(bem_surfaces)

    # 5. Persist artifacts
    mne.write_bem_surfaces(bem_surfaces_path, bem_surfaces, overwrite=config.overwrite)
    mne.write_bem_solution(bem_solution_path, bem_solution, overwrite=config.overwrite)

    return GeometryBEMOutput(
        subjects_dir=config.subjects_dir,
        subject_name=config.subject_name,
        bem_surfaces_path=bem_surfaces_path,
        bem_solution=bem_solution,
    )
