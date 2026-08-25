"""Unit tests for Step 0-C (Forward Model)."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock

import mne
import numpy as np

from modules.step0a_geometry_bem.output import GeometryBEMOutput
from modules.step0b_atlas_source.output import AtlasSourceOutput
from .main import run_forward_model
from .output import ForwardModelOutput
from .types import ForwardModelConfig


class TestStep0CForwardModel(unittest.TestCase):
    """Test suite for Step 0-C Forward Model computation."""

    def setUp(self):
        """Set up temporary directory and synthetic BEM and source space."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.subjects_dir = os.path.join(self.temp_dir.name, "subjects")
        self.subject_name = "icbm152"
        os.makedirs(self.subjects_dir, exist_ok=True)

        # Create synthetic sphere conductor model
        self.synthetic_bem = mne.make_sphere_model(
            r0=(0.0, 0.0, 0.0), head_radius=0.09, info=None, verbose=False
        )

        # Create synthetic source space inside the sphere
        self.synthetic_src = mne.setup_volume_source_space(
            pos=30.0, sphere=(0.0, 0.0, 0.0, 0.05), verbose=False
        )

        self.bem_out = GeometryBEMOutput(
            subjects_dir=self.subjects_dir,
            subject_name=self.subject_name,
            bem_surfaces_path="/path/to/bem.fif",
            bem_solution=self.synthetic_bem,
        )

        self.src_out = AtlasSourceOutput(
            src=self.synthetic_src,
            cerebra_labels=[],
            total_sources=int(sum(s["nuse"] for s in self.synthetic_src)),
            src_file_path="/path/to/src.fif",
        )

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_validation_none_bem_or_src(self):
        """Test that None BEM solution or source space raises ValueError."""
        bad_bem = GeometryBEMOutput(
            subjects_dir=self.subjects_dir,
            subject_name=self.subject_name,
            bem_surfaces_path="/path/to/bem.fif",
            bem_solution=None,  # type: ignore
        )
        config = ForwardModelConfig()
        with self.assertRaises(ValueError):
            run_forward_model(bad_bem, self.src_out, config)

        bad_src = AtlasSourceOutput(
            src=None,  # type: ignore
            cerebra_labels=[],
            total_sources=0,
            src_file_path="",
        )
        with self.assertRaises(ValueError):
            run_forward_model(self.bem_out, bad_src, config)

    def test_validation_invalid_channel_count(self):
        """Test that invalid channel count raises ValueError."""
        config_zero = ForwardModelConfig(eeg_channels_count=0)
        with self.assertRaises(ValueError):
            run_forward_model(self.bem_out, self.src_out, config_zero)

        config_too_many = ForwardModelConfig(
            montage_name="standard_1020",
            eeg_channels_count=500,
        )
        with self.assertRaises(ValueError):
            run_forward_model(self.bem_out, self.src_out, config_too_many)

    def test_validation_missing_subjects_dir(self):
        """Test that missing subjects_dir raises FileNotFoundError."""
        bad_bem = GeometryBEMOutput(
            subjects_dir="/path/to/non_existent_subjects_dir",
            subject_name=self.subject_name,
            bem_surfaces_path="/path/to/bem.fif",
            bem_solution=self.synthetic_bem,
        )
        config = ForwardModelConfig()
        with self.assertRaises(FileNotFoundError):
            run_forward_model(bad_bem, self.src_out, config)

    def test_run_forward_model_computation(self):
        """Test forward solution computation with synthetic inputs."""
        config = ForwardModelConfig(
            montage_name="GSN-HydroCel-128",
            eeg_channels_count=128,
            mindist=0.0,
            overwrite=True,
        )

        out = run_forward_model(self.bem_out, self.src_out, config)

        self.assertIsInstance(out, ForwardModelOutput)
        self.assertIsInstance(out.forward, mne.Forward)
        self.assertEqual(out.forward["nchan"], 128)
        self.assertEqual(out.forward["nsource"], self.src_out.total_sources)

        # Verify transformation matrix
        self.assertIsInstance(out.trans, mne.transforms.Transform)
        self.assertEqual(out.trans["from"], mne.io.constants.FIFF.FIFFV_COORD_HEAD)
        self.assertEqual(out.trans["to"], mne.io.constants.FIFF.FIFFV_COORD_MRI)
        np.testing.assert_array_almost_equal(out.trans["trans"], np.eye(4))

        # Verify info object
        self.assertEqual(len(out.info["ch_names"]), 128)
        self.assertTrue(os.path.exists(out.fwd_file_path))

    def test_run_forward_model_cached(self):
        """Test loading existing forward solution from disk."""
        config = ForwardModelConfig(
            montage_name="GSN-HydroCel-128",
            eeg_channels_count=128,
            mindist=0.0,
            overwrite=True,
        )
        out_first = run_forward_model(self.bem_out, self.src_out, config)
        self.assertTrue(os.path.exists(out_first.fwd_file_path))

        # Second call with overwrite=False should read from cache
        config_cached = ForwardModelConfig(
            montage_name="GSN-HydroCel-128",
            eeg_channels_count=128,
            mindist=0.0,
            overwrite=False,
        )
        out_cached = run_forward_model(self.bem_out, self.src_out, config_cached)

        self.assertEqual(out_cached.forward["nchan"], out_first.forward["nchan"])
        self.assertEqual(out_cached.forward["nsource"], out_first.forward["nsource"])
        self.assertEqual(out_cached.fwd_file_path, out_first.fwd_file_path)


if __name__ == "__main__":
    unittest.main()
