"""Unit tests for Step 2 Noise Covariance and Lambda2 calculation."""

import unittest
from dataclasses import FrozenInstanceError

import mne
import numpy as np

from modules.step1_preprocessing.output import PreprocessedEEGOutput
from modules.step2_noise_covariance.main import run_noise_covariance
from modules.step2_noise_covariance.output import CovarianceLambdaOutput
from modules.step2_noise_covariance.types import NoiseCovConfig


class TestNoiseCovariance(unittest.TestCase):
    """Test suite for noise covariance and dynamic lambda2 calculation."""

    def setUp(self) -> None:
        """Set up synthetic preprocessed EEG data."""
        self.sfreq = 125.0
        self.n_channels = 8
        self.n_samples = 1250  # 10 seconds
        ch_names = [f"EEG{i:03d}" for i in range(1, self.n_channels + 1)]
        info = mne.create_info(ch_names=ch_names, sfreq=self.sfreq, ch_types="eeg")

        rng = np.random.RandomState(42)
        data = rng.randn(self.n_channels, self.n_samples) * 1e-6

        self.raw = mne.io.RawArray(data, info)
        self.raw.set_eeg_reference("average", projection=True, verbose=False)

        self.eeg_out = PreprocessedEEGOutput(
            raw=self.raw,
            sampling_rate=self.sfreq,
            bad_channels=[],
            removed_ica_components=[]
        )

    def test_noise_cov_output_contract(self) -> None:
        """Verify that output matches CovarianceLambdaOutput schema and is immutable."""
        config = NoiseCovConfig(method="empirical")
        out = run_noise_covariance(self.eeg_out, config)

        self.assertIsInstance(out, CovarianceLambdaOutput)
        self.assertIsInstance(out.noise_cov, mne.Covariance)
        self.assertEqual(out.noise_cov.data.shape, (self.n_channels, self.n_channels))
        self.assertIsInstance(out.snr_db, float)
        self.assertIsInstance(out.lambda2, float)
        self.assertGreater(out.lambda2, 0.0)

        with self.assertRaises(FrozenInstanceError):
            out.snr_db = 10.0  # type: ignore

    def test_compute_snr_and_lambda2_math(self) -> None:
        """Verify that SNR and lambda2 mathematically match the analytical formula."""
        data = self.raw.get_data()
        power = np.mean(data ** 2, axis=0)
        p_mean = np.mean(power)
        sigma2 = np.var(power)
        expected_snr_db = float(10.0 * np.log10(p_mean / sigma2))
        expected_lambda2 = float(1.0 / (expected_snr_db ** 2))

        out = run_noise_covariance(self.eeg_out)

        self.assertAlmostEqual(out.snr_db, expected_snr_db, places=6)
        self.assertAlmostEqual(out.lambda2, expected_lambda2, places=6)

    def test_boundary_conditions_zero_data(self) -> None:
        """Verify fallback behavior for zero or constant signal."""
        info = mne.create_info(ch_names=[f"EEG{i:03d}" for i in range(1, 5)], sfreq=125.0, ch_types="eeg")
        zero_raw = mne.io.RawArray(np.zeros((4, 250)), info)
        zero_raw.set_eeg_reference("average", projection=True, verbose=False)

        zero_eeg_out = PreprocessedEEGOutput(
            raw=zero_raw,
            sampling_rate=125.0,
            bad_channels=[],
            removed_ica_components=[]
        )

        out = run_noise_covariance(zero_eeg_out)
        self.assertEqual(out.snr_db, 1.0)
        self.assertEqual(out.lambda2, 1.0)


if __name__ == "__main__":
    unittest.main()
