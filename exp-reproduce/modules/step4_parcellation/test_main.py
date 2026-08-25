"""
Unit tests for Step 4 (CerebrA Parcellation / MRA Extraction).
"""
import unittest
import mne
import numpy as np
import pandas as pd

from modules.step0b_atlas_source.output import AtlasSourceOutput
from modules.step3_source_localization.output import SourceEstimateOutput
from modules.step4_parcellation.main import run_parcellation
from modules.step4_parcellation.output import RegionalActivationOutput
from modules.step4_parcellation.types import SubjectMetadata


def _create_synthetic_source_space_and_labels(n_regions_per_hemi: int = 31):
    """Helper to generate synthetic SourceSpaces, Labels, and vertices."""
    lh_vertno = np.arange(0, n_regions_per_hemi * 2, dtype=int)
    rh_vertno = np.arange(0, n_regions_per_hemi * 2, dtype=int)

    lh_dict = {
        'vertno': lh_vertno,
        'type': 'surf',
        'hemi': 'lh',
        'inuse': np.ones(len(lh_vertno), dtype=int),
        'nuse': len(lh_vertno),
        'np': len(lh_vertno),
        'rr': np.zeros((len(lh_vertno), 3)),
        'nn': np.zeros((len(lh_vertno), 3)),
        'tris': np.zeros((1, 3), dtype=int),
        'ntri': 1
    }
    rh_dict = {
        'vertno': rh_vertno,
        'type': 'surf',
        'hemi': 'rh',
        'inuse': np.ones(len(rh_vertno), dtype=int),
        'nuse': len(rh_vertno),
        'np': len(rh_vertno),
        'rr': np.zeros((len(rh_vertno), 3)),
        'nn': np.zeros((len(rh_vertno), 3)),
        'tris': np.zeros((1, 3), dtype=int),
        'ntri': 1
    }
    src = mne.SourceSpaces([lh_dict, rh_dict])

    labels = []
    # LH labels
    for i in range(n_regions_per_hemi):
        lbl = mne.Label(
            vertices=np.array([2 * i, 2 * i + 1], dtype=int),
            hemi='lh',
            name=f"CerebrA_LH_Region_{i+1:02d}"
        )
        labels.append(lbl)

    # RH labels
    for i in range(n_regions_per_hemi):
        lbl = mne.Label(
            vertices=np.array([2 * i, 2 * i + 1], dtype=int),
            hemi='rh',
            name=f"CerebrA_RH_Region_{i+1:02d}"
        )
        labels.append(lbl)

    return src, labels, [lh_vertno, rh_vertno]


class TestStep4Parcellation(unittest.TestCase):
    """Test suite for step4_parcellation."""

    def setUp(self):
        """Set up synthetic test fixtures."""
        self.n_regions_per_hemi = 31
        self.total_regions = 62
        self.n_times = 100

        self.src, self.labels, self.vertices = _create_synthetic_source_space_and_labels(
            self.n_regions_per_hemi
        )
        self.total_sources = len(self.vertices[0]) + len(self.vertices[1])

        # Create reproducible positive synthetic STC data
        rng = np.random.default_rng(42)
        data = rng.uniform(0.5, 10.0, size=(self.total_sources, self.n_times))
        self.stc = mne.SourceEstimate(
            data=data,
            vertices=self.vertices,
            tmin=0.0,
            tstep=1.0 / 125.0
        )

        self.src_out = AtlasSourceOutput(
            src=self.src,
            cerebra_labels=self.labels,
            total_sources=self.total_sources
        )
        self.stc_out = SourceEstimateOutput(
            stc=self.stc,
            method="eLORETA",
            lambda2_used=0.1111
        )
        self.metadata = SubjectMetadata(
            subject_id="sub-01",
            condition="video1"
        )

    def test_parcellation_vectorized_shape(self):
        """Test output shape and schema of RegionalActivationOutput."""
        out = run_parcellation(self.stc_out, self.src_out, self.metadata)

        self.assertIsInstance(out, RegionalActivationOutput)
        self.assertIsInstance(out.mra_df, pd.DataFrame)
        self.assertEqual(len(out.mra_df), self.total_regions)
        self.assertEqual(len(out.region_names), self.total_regions)

        expected_cols = [
            "subject_id",
            "condition",
            "region_name",
            "mean_activation_na_m"
        ]
        self.assertListEqual(list(out.mra_df.columns), expected_cols)

        # Check metadata column contents
        self.assertTrue((out.mra_df["subject_id"] == "sub-01").all())
        self.assertTrue((out.mra_df["condition"] == "video1").all())
        self.assertListEqual(list(out.mra_df["region_name"]), out.region_names)

    def test_mra_non_negative_values(self):
        """Test that non-negative source estimates produce non-negative MRA values."""
        out = run_parcellation(self.stc_out, self.src_out, self.metadata)
        self.assertTrue((out.mra_df["mean_activation_na_m"] >= 0.0).all())
        self.assertFalse(out.mra_df["mean_activation_na_m"].isna().any())

    def test_mra_exact_vectorized_values(self):
        """Test that calculated MRA values match exact arithmetic expectations."""
        # Create STC with constant values per vertex:
        # Vertex i will have constant value (i + 1.0) for all time points
        const_data = np.zeros((self.total_sources, self.n_times))
        for v in range(self.total_sources):
            const_data[v, :] = float(v + 1)

        const_stc = mne.SourceEstimate(
            data=const_data,
            vertices=self.vertices,
            tmin=0.0,
            tstep=1.0 / 125.0
        )
        const_stc_out = SourceEstimateOutput(
            stc=const_stc,
            method="eLORETA",
            lambda2_used=0.1
        )

        out = run_parcellation(const_stc_out, self.src_out, self.metadata)

        # For LH region i: vertices are (2*i, 2*i + 1)
        # vertex indices 2*i and 2*i+1 have values (2*i + 1) and (2*i + 2)
        # mean across vertices = 2*i + 1.5
        for i in range(self.n_regions_per_hemi):
            expected_val = (2 * i + 1 + 2 * i + 2) / 2.0
            actual_val = out.mra_df.iloc[i]["mean_activation_na_m"]
            self.assertAlmostEqual(actual_val, expected_val, places=5)

    def test_empty_labels_raises_error(self):
        """Test that empty labels list raises ValueError."""
        empty_src_out = AtlasSourceOutput(
            src=self.src,
            cerebra_labels=[],
            total_sources=self.total_sources
        )
        with self.assertRaises(ValueError):
            run_parcellation(self.stc_out, empty_src_out, self.metadata)

    def test_nan_in_stc_raises_error(self):
        """Test that NaN values in STC trigger ValueError."""
        nan_data = self.stc.data.copy()
        nan_data[0, 0] = np.nan
        nan_stc = mne.SourceEstimate(
            data=nan_data,
            vertices=self.vertices,
            tmin=0.0,
            tstep=1.0 / 125.0
        )
        nan_stc_out = SourceEstimateOutput(
            stc=nan_stc,
            method="eLORETA",
            lambda2_used=0.1
        )
        with self.assertRaises(ValueError):
            run_parcellation(nan_stc_out, self.src_out, self.metadata)


if __name__ == "__main__":
    unittest.main()
