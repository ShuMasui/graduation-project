"""Unit tests for Step 0-A (Geometry & BEM)."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import mne

from .main import run_geometry_bem
from .output import GeometryBEMOutput
from .types import GeometryBEMConfig


class TestStep0AGeometryBEM(unittest.TestCase):
    """Test suite for Step 0-A Geometry & BEM computation."""

    def setUp(self):
        """Set up temporary directories and dummy files for tests."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.subjects_dir = os.path.join(self.temp_dir.name, "subjects")
        os.makedirs(self.subjects_dir, exist_ok=True)

        # Create a dummy template NIfTI file
        self.dummy_nii = os.path.join(self.temp_dir.name, "template.nii")
        with open(self.dummy_nii, "w") as f:
            f.write("dummy nifti content")

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_config_validation_missing_file(self):
        """Test that missing template NIfTI file raises FileNotFoundError."""
        config = GeometryBEMConfig(
            template_nii_path="/path/to/non_existent_file.nii",
            subjects_dir=self.subjects_dir,
            subject_name="icbm152",
        )
        with self.assertRaises(FileNotFoundError):
            run_geometry_bem(config)

    def test_config_validation_invalid_conductivity(self):
        """Test that invalid conductivity values raise ValueError."""
        # Non-positive conductivity
        config_neg = GeometryBEMConfig(
            template_nii_path=self.dummy_nii,
            subjects_dir=self.subjects_dir,
            conductivity=(0.33, -0.0042, 0.33),
        )
        with self.assertRaises(ValueError):
            run_geometry_bem(config_neg)

        # Invalid length
        config_len = GeometryBEMConfig(
            template_nii_path=self.dummy_nii,
            subjects_dir=self.subjects_dir,
            conductivity=(0.33, 0.33),  # type: ignore
        )
        with self.assertRaises(ValueError):
            run_geometry_bem(config_len)

    def test_config_validation_invalid_resolution(self):
        """Test that invalid ico_resolution raises ValueError."""
        config = GeometryBEMConfig(
            template_nii_path=self.dummy_nii,
            subjects_dir=self.subjects_dir,
            ico_resolution=0,
        )
        with self.assertRaises(ValueError):
            run_geometry_bem(config)

    @patch("mne.read_bem_solution")
    def test_run_geometry_bem_cached(self, mock_read_bem):
        """Test that cached BEM solution is loaded when available."""
        mock_conductor = MagicMock(spec=mne.bem.ConductorModel)
        mock_read_bem.return_value = mock_conductor

        subject_name = "icbm152"
        bem_dir = os.path.join(self.subjects_dir, subject_name, "bem")
        os.makedirs(bem_dir, exist_ok=True)
        sol_path = os.path.join(bem_dir, f"{subject_name}-5120-bem-sol.fif")
        with open(sol_path, "w") as f:
            f.write("mock bem sol")

        config = GeometryBEMConfig(
            template_nii_path=self.dummy_nii,
            subjects_dir=self.subjects_dir,
            subject_name=subject_name,
            overwrite=False,
        )

        out = run_geometry_bem(config)

        mock_read_bem.assert_called_once_with(sol_path)
        self.assertIsInstance(out, GeometryBEMOutput)
        self.assertEqual(out.subjects_dir, self.subjects_dir)
        self.assertEqual(out.subject_name, subject_name)
        self.assertEqual(out.bem_solution, mock_conductor)

    @patch("mne.bem.make_watershed_bem")
    @patch("mne.make_bem_model")
    @patch("mne.make_bem_solution")
    @patch("mne.write_bem_surfaces")
    @patch("mne.write_bem_solution")
    def test_run_geometry_bem_full_pipeline(
        self,
        mock_write_sol,
        mock_write_surfs,
        mock_make_sol,
        mock_make_model,
        mock_watershed,
    ):
        """Test full BEM generation workflow with mocked underlying MNE functions."""
        mock_bem_model = MagicMock()
        mock_conductor = MagicMock(spec=mne.bem.ConductorModel)
        mock_make_model.return_value = mock_bem_model
        mock_make_sol.return_value = mock_conductor

        config = GeometryBEMConfig(
            template_nii_path=self.dummy_nii,
            subjects_dir=self.subjects_dir,
            subject_name="icbm152",
            overwrite=True,
        )

        out = run_geometry_bem(config)

        mock_watershed.assert_called_once_with(
            subject="icbm152",
            subjects_dir=self.subjects_dir,
            overwrite=True,
        )
        mock_make_model.assert_called_once_with(
            subject="icbm152",
            ico=4,
            conductivity=[0.33, 0.0042, 0.33],
            subjects_dir=self.subjects_dir,
        )
        mock_make_sol.assert_called_once_with(mock_bem_model)
        mock_write_surfs.assert_called_once()
        mock_write_sol.assert_called_once()

        self.assertIsInstance(out, GeometryBEMOutput)
        self.assertEqual(out.subject_name, "icbm152")
        self.assertEqual(out.bem_solution, mock_conductor)


if __name__ == "__main__":
    unittest.main()
