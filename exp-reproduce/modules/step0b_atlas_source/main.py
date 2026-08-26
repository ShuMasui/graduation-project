"""Core logic for Step 0-B: CerebrA atlas conversion & source space generation."""
import os
from typing import List

import mne
import nibabel as nib
import numpy as np
import pandas as pd

from modules.step0a_geometry_bem.output import GeometryBEMOutput
from .output import AtlasSourceOutput
from .types import AtlasSourceConfig


def run_atlas_source(
    bem_out: GeometryBEMOutput, config: AtlasSourceConfig
) -> AtlasSourceOutput:
    """Generate cortical source space and extract CerebrA cortical labels.

    Args:
        bem_out: Output DTO from Step 0-A containing subjects directory and subject name.
        config: Configuration containing CerebrA NIfTI and CSV paths, grid spacing, etc.

    Returns:
        AtlasSourceOutput containing the source space, list of 62 CerebrA Label objects,
        and total active source count.

    Raises:
        FileNotFoundError: If the CerebrA NIfTI or CSV file is not found, or if
            the subjects directory does not exist.
        ValueError: If source space generation fails or input atlas data is empty.
    """
    # 1. Input validation
    if not os.path.exists(config.cerebra_nii_path):
        raise FileNotFoundError(
            f"CerebrA NIfTI file not found: {config.cerebra_nii_path}"
        )

    if not os.path.exists(config.cerebra_csv_path):
        raise FileNotFoundError(
            f"CerebrA CSV file not found: {config.cerebra_csv_path}"
        )

    if not os.path.exists(bem_out.subjects_dir):
        raise FileNotFoundError(
            f"Subjects directory not found: {bem_out.subjects_dir}"
        )

    # 2. Source Space setup / caching
    src_dir = os.path.join(bem_out.subjects_dir, bem_out.subject_name, "bem")
    os.makedirs(src_dir, exist_ok=True)
    src_file_path = os.path.join(
        src_dir, f"{bem_out.subject_name}-{config.spacing}-src.fif"
    )

    if not config.overwrite and os.path.exists(src_file_path):
        src = mne.read_source_spaces(src_file_path)
    else:
        src = mne.setup_source_space(
            subject=bem_out.subject_name,
            spacing=config.spacing,
            surface=config.surface,
            subjects_dir=bem_out.subjects_dir,
        )
        mne.write_source_spaces(src_file_path, src, overwrite=config.overwrite)

    total_sources = int(sum(s["nuse"] for s in src))

    # 3. CerebrA Atlas CSV metadata loading
    df = pd.read_csv(config.cerebra_csv_path)
    if "Mindboggle ID" in df.columns:
        cortical_df = df[df["Mindboggle ID"] >= 2000]
        if len(cortical_df) == 0:
            cortical_df = df
    else:
        cortical_df = df

    lh_col = "LH Labels" if "LH Labels" in cortical_df.columns else "LH Label"
    rh_col = "RH Label" if "RH Label" in cortical_df.columns else "RH Labels"
    name_col = "Label Name" if "Label Name" in cortical_df.columns else "Region Name"

    # 4. CerebrA NIfTI voxel loading and coordinate transformation
    img = nib.load(config.cerebra_nii_path)
    voxel_data = np.asanyarray(img.dataobj)
    inv_affine = np.linalg.inv(img.affine)

    cerebra_labels: List[mne.Label] = []

    # Map LH vertices to CerebrA labels
    if len(src) >= 1:
        rr_lh = src[0]["rr"]
        rr_lh_mm = rr_lh * 1000.0  # MNE surface coordinates are in meters
        coords_homo_lh = np.hstack([rr_lh_mm, np.ones((len(rr_lh_mm), 1))])
        vox_lh = np.rint(coords_homo_lh @ inv_affine.T[:, :3]).astype(int)
        valid_lh = (
            (vox_lh[:, 0] >= 0)
            & (vox_lh[:, 0] < voxel_data.shape[0])
            & (vox_lh[:, 1] >= 0)
            & (vox_lh[:, 1] < voxel_data.shape[1])
            & (vox_lh[:, 2] >= 0)
            & (vox_lh[:, 2] < voxel_data.shape[2])
        )
        sampled_lh = np.zeros(len(rr_lh), dtype=int)
        sampled_lh[valid_lh] = voxel_data[
            vox_lh[valid_lh, 0], vox_lh[valid_lh, 1], vox_lh[valid_lh, 2]
        ]
    else:
        rr_lh = np.empty((0, 3))
        sampled_lh = np.empty((0,), dtype=int)

    # Map RH vertices to CerebrA labels
    if len(src) >= 2:
        rr_rh = src[1]["rr"]
        rr_rh_mm = rr_rh * 1000.0
        coords_homo_rh = np.hstack([rr_rh_mm, np.ones((len(rr_rh_mm), 1))])
        vox_rh = np.rint(coords_homo_rh @ inv_affine.T[:, :3]).astype(int)
        valid_rh = (
            (vox_rh[:, 0] >= 0)
            & (vox_rh[:, 0] < voxel_data.shape[0])
            & (vox_rh[:, 1] >= 0)
            & (vox_rh[:, 1] < voxel_data.shape[1])
            & (vox_rh[:, 2] >= 0)
            & (vox_rh[:, 2] < voxel_data.shape[2])
        )
        sampled_rh = np.zeros(len(rr_rh), dtype=int)
        sampled_rh[valid_rh] = voxel_data[
            vox_rh[valid_rh, 0], vox_rh[valid_rh, 1], vox_rh[valid_rh, 2]
        ]
    else:
        rr_rh = np.empty((0, 3))
        sampled_rh = np.empty((0,), dtype=int)

    for _, row in cortical_df.iterrows():
        region_name = str(row[name_col]).strip()

        # LH Label
        lh_id = int(row[lh_col])
        lh_vert = np.where(sampled_lh == lh_id)[0]
        lh_pos = rr_lh[lh_vert] if len(lh_vert) > 0 else np.empty((0, 3))
        lh_label = mne.Label(
            vertices=lh_vert,
            pos=lh_pos,
            values=np.ones(len(lh_vert)),
            hemi="lh",
            name=f"{region_name}-lh",
            subject=bem_out.subject_name,
        )
        cerebra_labels.append(lh_label)

        # RH Label
        rh_id = int(row[rh_col])
        rh_vert = np.where(sampled_rh == rh_id)[0]
        rh_pos = rr_rh[rh_vert] if len(rh_vert) > 0 else np.empty((0, 3))
        rh_label = mne.Label(
            vertices=rh_vert,
            pos=rh_pos,
            values=np.ones(len(rh_vert)),
            hemi="rh",
            name=f"{region_name}-rh",
            subject=bem_out.subject_name,
        )
        cerebra_labels.append(rh_label)

    return AtlasSourceOutput(
        src=src,
        cerebra_labels=cerebra_labels,
        total_sources=total_sources,
        src_file_path=src_file_path,
    )
