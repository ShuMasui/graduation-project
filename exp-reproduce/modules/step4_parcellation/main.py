"""
Step 4: CerebrA Regional Aggregation (Mean Regional Activation: MRA).

This module extracts and aggregates source-space cortical estimates across
CerebrA atlas parcels (62 regions) using spatial and temporal vectorization.
"""
from typing import List
import mne
import numpy as np
import pandas as pd

from modules.step0b_atlas_source.output import AtlasSourceOutput
from modules.step3_source_localization.output import SourceEstimateOutput
from .output import RegionalActivationOutput
from .types import SubjectMetadata


def run_parcellation(
    stc_out: SourceEstimateOutput,
    src_out: AtlasSourceOutput,
    metadata: SubjectMetadata
) -> RegionalActivationOutput:
    """Extract and aggregate source time courses into Mean Regional Activation (MRA).

    Computes spatial average for each CerebrA region across vertices, followed by
    vectorized temporal averaging across the analysis time window.

    Parameters:
        stc_out: Output from Step 3 containing source estimate (stc).
        src_out: Output from Step 0-B containing source spaces and CerebrA labels.
        metadata: Subject and experimental condition metadata.

    Returns:
        RegionalActivationOutput containing tidy DataFrame and region names.

    Raises:
        ValueError: If cerebra_labels is empty, or if computed MRA values contain
                    NaN/Inf, or if row counts do not match label counts.
    """
    labels: List[mne.Label] = src_out.cerebra_labels
    if not labels:
        raise ValueError("cerebra_labels in AtlasSourceOutput is empty.")

    # 1. Spatial aggregation across vertices for each label
    # mne.extract_label_time_course returns a 2D ndarray of shape (n_labels, n_times)
    label_tc = mne.extract_label_time_course(
        stcs=stc_out.stc,
        labels=labels,
        src=src_out.src,
        mode=metadata.extract_mode,
        verbose=False
    )

    # 2. Vectorized temporal average across time axis (axis=1) without for-loops
    # Resulting shape: (n_labels,)
    mra_values = np.mean(label_tc, axis=1)

    # 3. Boundary checks and validation
    if not np.isfinite(mra_values).all():
        raise ValueError("Calculated MRA values contain NaN or Inf values.")

    region_names: List[str] = [
        label.name if label.name is not None else f"region_{idx}"
        for idx, label in enumerate(labels)
    ]

    if len(mra_values) != len(region_names):
        raise ValueError(
            f"MRA values count ({len(mra_values)}) does not match "
            f"region names count ({len(region_names)})."
        )

    # 4. Construct Tidy DataFrame
    mra_df = pd.DataFrame({
        "subject_id": metadata.subject_id,
        "condition": metadata.condition,
        "region_name": region_names,
        "mean_activation_na_m": mra_values
    })

    return RegionalActivationOutput(
        mra_df=mra_df,
        region_names=region_names
    )
