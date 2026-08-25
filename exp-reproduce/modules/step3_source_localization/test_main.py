"""Unit tests for Step 3 eLORETA Source Localization."""

import unittest
from dataclasses import FrozenInstanceError

import mne
from mne.io.constants import FIFF
import numpy as np

from modules.step0c_forward_model.output import ForwardModelOutput
from modules.step1_preprocessing.output import PreprocessedEEGOutput
from modules.step2_noise_covariance.output import CovarianceLambdaOutput
from modules.step3_source_localization.main import run_source_localization
from modules.step3_source_localization.output import SourceEstimateOutput
from modules.step3_source_localization.types import SourceLocConfig


def _create_synthetic_source_space() -> mne.SourceSpaces:
    """Create a synthetic surface source space on a sphere."""
    surf = mne.bem._get_ico_surface(3)
    rr = surf["rr"] * 0.06  # 60 mm radius
    tris = surf["tris"]
    nn = surf["nn"]

    lh = {
        "rr": rr,
        "tris": tris,
        "nn": nn,
        "inuse": np.ones(len(rr), dtype=np.int32),
        "nuse": len(rr),
        "vertno": np.arange(len(rr), dtype=np.int32),
        "coord_frame": FIFF.FIFFV_COORD_MRI,
        "id": FIFF.FIFFV_MNE_SURF_LEFT_HEMI,
        "type": "surf",
        "np": len(rr),
        "use_tris": tris,
        "subject_his_id": "sample",
    }
    rh = {
        "rr": rr + np.array([0.001, 0.0, 0.0]),
        "tris": tris,
        "nn": nn,
        "inuse": np.ones(len(rr), dtype=np.int32),
        "nuse": len(rr),
        "vertno": np.arange(len(rr), dtype=np.int32),
        "coord_frame": FIFF.FIFFV_COORD_MRI,
        "id": FIFF.FIFFV_MNE_SURF_RIGHT_HEMI,
        "type": "surf",
        "np": len(rr),
        "use_tris": tris,
        "subject_his_id": "sample",
    }
    return mne.SourceSpaces([lh, rh])


class TestSourceLocalization(unittest.TestCase):
    """Test suite for eLORETA source localization."""

    @classmethod
    def setUpClass(cls) -> None:
        """Construct synthetic forward model, raw EEG, and noise covariance objects."""
        cls.sfreq = 125.0
        cls.n_channels = 8
        cls.n_times = 250  # 2.0 seconds

        # 1. Montage and Info
        montage = mne.channels.make_standard_montage("standard_1020")
        ch_names = ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4"]
        cls.info = mne.create_info(ch_names=ch_names, sfreq=cls.sfreq, ch_types="eeg")
        cls.info.set_montage(montage)

        # 2. Source space & Sphere BEM
        src = _create_synthetic_source_space()
        sphere = mne.make_sphere_model(r0=(0.0, 0.0, 0.0), head_radius=0.09, info=None, verbose=False)
        cls.trans = mne.transforms.Transform("head", "mri", np.eye(4))

        fwd = mne.make_forward_solution(
            cls.info,
            trans=cls.trans,
            src=src,
            bem=sphere,
            eeg=True,
            meg=False,
            mindist=2.0,
            verbose=False
        )
        cls.fwd_out = ForwardModelOutput(
            forward=fwd,
            trans=cls.trans,
            info=cls.info,
            fwd_file_path=""
        )

        # 3. Synthetic Preprocessed EEG
        rng = np.random.RandomState(42)
        data = rng.randn(cls.n_channels, cls.n_times) * 1e-6
        cls.raw = mne.io.RawArray(data, cls.info)
        cls.raw.set_eeg_reference("average", projection=True, verbose=False)

        cls.eeg_out = PreprocessedEEGOutput(
            raw=cls.raw,
            sampling_rate=cls.sfreq,
            bad_channels=[],
            removed_ica_components=[]
        )

        # 4. Noise Covariance
        cov = mne.compute_raw_covariance(cls.raw, verbose=False)
        cls.cov_out = CovarianceLambdaOutput(
            noise_cov=cov,
            snr_db=10.0,
            lambda2=0.01
        )

    def test_run_source_localization_synthetic(self) -> None:
        """Verify eLORETA execution and output dimensionality."""
        config = SourceLocConfig(method="eLORETA", loose=0.2, depth=0.8)
        out = run_source_localization(
            fwd_out=self.fwd_out,
            eeg_out=self.eeg_out,
            cov_out=self.cov_out,
            config=config
        )

        self.assertIsInstance(out, SourceEstimateOutput)
        self.assertIsInstance(out.stc, mne.SourceEstimate)
        self.assertEqual(out.method, "eLORETA")
        self.assertEqual(out.lambda2_used, 0.01)

        # Verify dimensions: (n_sources, n_times)
        n_sources = self.fwd_out.forward["nsource"]
        self.assertEqual(out.stc.data.shape, (n_sources, self.n_times))
        self.assertFalse(np.isnan(out.stc.data).any())
        self.assertFalse(np.isinf(out.stc.data).any())

    def test_output_immutability(self) -> None:
        """Verify that SourceEstimateOutput is frozen."""
        out = run_source_localization(
            fwd_out=self.fwd_out,
            eeg_out=self.eeg_out,
            cov_out=self.cov_out
        )
        with self.assertRaises(FrozenInstanceError):
            out.method = "dSPM"  # type: ignore

    def test_custom_source_loc_config(self) -> None:
        """Verify that custom configuration parameters are applied without errors."""
        config = SourceLocConfig(method="eLORETA", loose=0.5, depth=0.5)
        out = run_source_localization(
            fwd_out=self.fwd_out,
            eeg_out=self.eeg_out,
            cov_out=self.cov_out,
            config=config
        )
        self.assertEqual(out.method, "eLORETA")
        self.assertEqual(out.stc.data.shape[1], self.n_times)


if __name__ == "__main__":
    unittest.main()
