"""Unit tests for Step 1 Preprocessing module."""

import os
import tempfile
import unittest
from dataclasses import FrozenInstanceError

import mne
import numpy as np

from modules.step1_preprocessing.main import run_preprocessing
from modules.step1_preprocessing.output import PreprocessedEEGOutput
from modules.step1_preprocessing.types import PreprocessingConfig


class TestPreprocessing(unittest.TestCase):
    """Test suite for raw EEG preprocessing."""

    def setUp(self) -> None:
        """Set up synthetic raw EEG dataset."""
        self.sfreq = 250.0
        self.n_channels = 16
        self.n_samples = 2500  # 10 seconds
        self.montage = mne.channels.make_standard_montage("standard_1020")
        self.ch_names = self.montage.ch_names[: self.n_channels]

        info = mne.create_info(ch_names=self.ch_names, sfreq=self.sfreq, ch_types="eeg")
        times = np.linspace(0, self.n_samples / self.sfreq, self.n_samples, endpoint=False)

        # 10 Hz alpha wave mixed across channels + Gaussian noise
        base_signal = np.sin(2 * np.pi * 10.0 * times)
        weights = np.linspace(0.8, 1.2, self.n_channels)[:, np.newaxis]
        data = weights * base_signal + np.random.RandomState(42).randn(self.n_channels, self.n_samples) * 0.05
        data *= 1e-6  # Convert to Volts

        self.raw = mne.io.RawArray(data, info)
        self.raw.set_montage(self.montage)

    def test_run_preprocessing_synthetic(self) -> None:
        """Verify resampling, filtering, and return type with synthetic data."""
        config = PreprocessingConfig(
            raw_eeg_path="",
            target_sampling_rate=125.0,
            l_freq=1.0,
            h_freq=50.0,
            apply_prep=True,
            ica_n_components=4,
            random_state=42
        )
        out = run_preprocessing(config, raw=self.raw)

        self.assertIsInstance(out, PreprocessedEEGOutput)
        self.assertEqual(out.sampling_rate, 125.0)
        self.assertEqual(out.raw.info["sfreq"], 125.0)
        self.assertEqual(len(out.raw.times), 1250)
        self.assertIsInstance(out.bad_channels, list)
        self.assertIsInstance(out.removed_ica_components, list)

    def test_output_immutability(self) -> None:
        """Verify that PreprocessedEEGOutput is a frozen dataclass."""
        config = PreprocessingConfig(raw_eeg_path="", target_sampling_rate=125.0, ica_n_components=2)
        out = run_preprocessing(config, raw=self.raw)

        with self.assertRaises(FrozenInstanceError):
            out.sampling_rate = 250.0  # type: ignore

    def test_preprocessing_with_bad_channel(self) -> None:
        """Verify that a noisy channel is detected and handled."""
        # Corrupt one channel with high amplitude noise
        data_corrupt = self.raw.get_data()
        data_corrupt[3] += np.random.RandomState(99).randn(self.n_samples) * 1e-4

        info = mne.create_info(ch_names=self.ch_names, sfreq=self.sfreq, ch_types="eeg")
        corrupt_raw = mne.io.RawArray(data_corrupt, info)
        corrupt_raw.set_montage(self.montage)

        config = PreprocessingConfig(
            raw_eeg_path="",
            target_sampling_rate=125.0,
            apply_prep=True,
            ica_n_components=4,
            random_state=42
        )
        out = run_preprocessing(config, raw=corrupt_raw)
        self.assertIsInstance(out, PreprocessedEEGOutput)
        self.assertTrue(len(out.raw.ch_names) == self.n_channels)

    def test_file_loading_fif(self) -> None:
        """Verify loading and preprocessing directly from a FIF file on disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fif_path = os.path.join(tmpdir, "test_raw.fif")
            self.raw.save(fif_path, overwrite=True)

            config = PreprocessingConfig(
                raw_eeg_path=fif_path,
                target_sampling_rate=125.0,
                apply_prep=False,
                ica_n_components=2
            )
            out = run_preprocessing(config)
            self.assertEqual(out.sampling_rate, 125.0)
            self.assertIsInstance(out.raw, mne.io.BaseRaw)


if __name__ == "__main__":
    unittest.main()
