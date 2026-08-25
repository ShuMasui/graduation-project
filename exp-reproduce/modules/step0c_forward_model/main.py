"""Core logic for Step 0-C: Electrode co-registration & forward model computation."""
import os
import mne
import numpy as np

from modules.step0a_geometry_bem.output import GeometryBEMOutput
from modules.step0b_atlas_source.output import AtlasSourceOutput
from .output import ForwardModelOutput
from .types import ForwardModelConfig


def run_forward_model(
    bem_out: GeometryBEMOutput,
    src_out: AtlasSourceOutput,
    config: ForwardModelConfig,
) -> ForwardModelOutput:
    """Co-register standard montage to head geometry and compute forward solution.

    Args:
        bem_out: Output DTO from Step 0-A containing BEM conductor model.
        src_out: Output DTO from Step 0-B containing source space.
        config: Configuration containing montage name, channel count, mindist, etc.

    Returns:
        ForwardModelOutput containing the Lead Field matrix (Forward),
        coordinate transformation (trans), and montage info.

    Raises:
        ValueError: If BEM solution or source space is None, or channel count is invalid.
        FileNotFoundError: If the subjects directory does not exist.
    """
    # 1. Input validation
    if bem_out.bem_solution is None:
        raise ValueError("BEM solution cannot be None.")

    if src_out.src is None:
        raise ValueError("Source space cannot be None.")

    if config.eeg_channels_count <= 0:
        raise ValueError(
            f"eeg_channels_count must be positive, got: {config.eeg_channels_count}"
        )

    if not os.path.exists(bem_out.subjects_dir):
        raise FileNotFoundError(
            f"Subjects directory not found: {bem_out.subjects_dir}"
        )

    # 2. Montage and measurement info setup
    montage = mne.channels.make_standard_montage(config.montage_name)
    if len(montage.ch_names) < config.eeg_channels_count:
        raise ValueError(
            f"Montage {config.montage_name} contains only {len(montage.ch_names)} channels, "
            f"but {config.eeg_channels_count} channels were requested."
        )

    ch_names = montage.ch_names[:config.eeg_channels_count]
    info = mne.create_info(ch_names=ch_names, sfreq=125.0, ch_types="eeg")
    info.set_montage(montage)

    # 3. Coordinate transformation matrix (head -> MRI RAS)
    # Standard template coordinate systems are aligned with the template MRI RAS.
    trans = mne.transforms.Transform("head", "mri", np.eye(4))

    # 4. Cache verification
    fwd_dir = os.path.join(bem_out.subjects_dir, bem_out.subject_name, "bem")
    os.makedirs(fwd_dir, exist_ok=True)
    fwd_file_path = os.path.join(
        fwd_dir, f"{bem_out.subject_name}-{config.montage_name}-fwd.fif"
    )

    if not config.overwrite and os.path.exists(fwd_file_path):
        forward = mne.read_forward_solution(fwd_file_path)
        return ForwardModelOutput(
            forward=forward,
            trans=trans,
            info=info,
            fwd_file_path=fwd_file_path,
        )

    # 5. Compute forward solution
    forward = mne.make_forward_solution(
        info=info,
        trans=trans,
        src=src_out.src,
        bem=bem_out.bem_solution,
        eeg=True,
        meg=False,
        mindist=config.mindist,
        n_jobs=config.n_jobs,
    )

    # 6. Save forward solution to disk
    mne.write_forward_solution(fwd_file_path, forward, overwrite=config.overwrite)

    return ForwardModelOutput(
        forward=forward,
        trans=trans,
        info=info,
        fwd_file_path=fwd_file_path,
    )
