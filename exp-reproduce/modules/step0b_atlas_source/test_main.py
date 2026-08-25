"""Unit tests for Step 0-B (Atlas & Source Space)."""
import copy
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import mne
import nibabel as nib
import numpy as np
import pandas as pd

from modules.step0a_geometry_bem.output import GeometryBEMOutput
from .main import run_atlas_source
from .output import AtlasSourceOutput
from .types import AtlasSourceConfig


def _create_synthetic_source_space(pos: float = 30.0) -> mne.SourceSpaces:
    """Helper to create a synthetic 2-hemisphere SourceSpaces object."""
    base_src = mne.setup_volume_source_space(pos=pos, sphere=(0.0, 0.0, 0.0, 0.05), verbose=False)
    lh_src = copy.deepcopy(base_src[0])
    rh_src = copy.deepcopy(base_src[0])
    lh_src["id"] = 101
    lh_src["type"] = "surf"
    rh_src["id"] = 102
    rh_src["type"] = "surf"
    return mne.SourceSpaces([lh_src, rh_src])


class TestStep0BAtlasSource(unittest.TestCase):
    """Test suite for Step 0-B Atlas & Source Space generation."""

    def setUp(self):
        """Set up temporary directory, synthetic NIfTI, and dummy CSV."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.subjects_dir = os.path.join(self.temp_dir.name, "subjects")
        self.subject_name = "icbm152"
        os.makedirs(self.subjects_dir, exist_ok=True)

        # Create dummy NIfTI volume
        vol = np.zeros((30, 30, 30), dtype=np.int32)
        vol[10:20, 10:20, 10:20] = 81  # Caudal Anterior Cingulate LH
        vol[5:10, 5:10, 5:10] = 30     # Caudal Anterior Cingulate RH
        affine = np.diag([2.0, 2.0, 2.0, 1.0])
        affine[:3, 3] = [-30, -30, -30]
        self.dummy_nii_path = os.path.join(self.temp_dir.name, "CerebrA.nii")
        nib.save(nib.Nifti1Image(vol, affine), self.dummy_nii_path)

        # Create realistic CSV with 31 cortical areas
        cortical_records = []
        for i in range(31):
            cortical_records.append({
                "Mindboggle ID": 2002 + i,
                "Label Name": f"Region_{i+1}",
                "RH Label": 1 + i,
                "LH Labels": 52 + i,
                "Notes": "",
                "Dice Kappa": 0.8,
            })
        self.dummy_csv_path = os.path.join(self.temp_dir.name, "CerebrA.csv")
        pd.DataFrame(cortical_records).to_csv(self.dummy_csv_path, index=False)

        # Mock Step 0-A output
        mock_bem_model = MagicMock(spec=mne.bem.ConductorModel)
        self.bem_out = GeometryBEMOutput(
            subjects_dir=self.subjects_dir,
            subject_name=self.subject_name,
            bem_surfaces_path="/path/to/bem.fif",
            bem_solution=mock_bem_model,
        )

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_config_validation_missing_nii(self):
        """Test that missing NIfTI file raises FileNotFoundError."""
        config = AtlasSourceConfig(
            cerebra_nii_path="/path/to/non_existent.nii",
            cerebra_csv_path=self.dummy_csv_path,
        )
        with self.assertRaises(FileNotFoundError):
            run_atlas_source(self.bem_out, config)

    def test_config_validation_missing_csv(self):
        """Test that missing CSV file raises FileNotFoundError."""
        config = AtlasSourceConfig(
            cerebra_nii_path=self.dummy_nii_path,
            cerebra_csv_path="/path/to/non_existent.csv",
        )
        with self.assertRaises(FileNotFoundError):
            run_atlas_source(self.bem_out, config)

    def test_config_validation_missing_subjects_dir(self):
        """Test that missing subjects_dir raises FileNotFoundError."""
        bad_bem_out = GeometryBEMOutput(
            subjects_dir="/path/to/non_existent_subjects_dir",
            subject_name=self.subject_name,
            bem_surfaces_path="/path/to/bem.fif",
            bem_solution=self.bem_out.bem_solution,
        )
        config = AtlasSourceConfig(
            cerebra_nii_path=self.dummy_nii_path,
            cerebra_csv_path=self.dummy_csv_path,
        )
        with self.assertRaises(FileNotFoundError):
            run_atlas_source(bad_bem_out, config)

    @patch("mne.setup_source_space")
    def test_run_atlas_source_with_synthetic_data(self, mock_setup_src):
        """Test source space generation and 62 CerebrA label extraction."""
        synthetic_src = _create_synthetic_source_space(pos=30.0)
        mock_setup_src.return_value = synthetic_src

        config = AtlasSourceConfig(
            cerebra_nii_path=self.dummy_nii_path,
            cerebra_csv_path=self.dummy_csv_path,
            spacing="oct6",
            surface="white",
            overwrite=True,
        )

        out = run_atlas_source(self.bem_out, config)

        self.assertIsInstance(out, AtlasSourceOutput)
        self.assertEqual(out.total_sources, synthetic_src[0]["nuse"] + synthetic_src[1]["nuse"])
        self.assertEqual(len(out.cerebra_labels), 62)

        # Check LH and RH counts
        lh_labels = [l for l in out.cerebra_labels if l.hemi == "lh"]
        rh_labels = [l for l in out.cerebra_labels if l.hemi == "rh"]
        self.assertEqual(len(lh_labels), 31)
        self.assertEqual(len(rh_labels), 31)

        for lbl in out.cerebra_labels:
            self.assertIsInstance(lbl, mne.Label)
            self.assertEqual(lbl.subject, self.subject_name)

    def test_run_atlas_source_cached(self):
        """Test loading cached source spaces from disk."""
        synthetic_src = _create_synthetic_source_space(pos=30.0)
        src_dir = os.path.join(self.subjects_dir, self.subject_name, "bem")
        os.makedirs(src_dir, exist_ok=True)
        cached_src_path = os.path.join(
            src_dir, f"{self.subject_name}-oct6-src.fif"
        )
        mne.write_source_spaces(cached_src_path, synthetic_src, overwrite=True)

        config = AtlasSourceConfig(
            cerebra_nii_path=self.dummy_nii_path,
            cerebra_csv_path=self.dummy_csv_path,
            spacing="oct6",
            surface="white",
            overwrite=False,
        )

        out = run_atlas_source(self.bem_out, config)

        self.assertIsInstance(out, AtlasSourceOutput)
        self.assertEqual(out.total_sources, synthetic_src[0]["nuse"] + synthetic_src[1]["nuse"])
        self.assertEqual(len(out.cerebra_labels), 62)
        self.assertEqual(out.src_file_path, cached_src_path)


if __name__ == "__main__":
    unittest.main()
