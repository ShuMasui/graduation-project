"""Step 1: Raw EEG Preprocessing logic."""

from typing import List, Optional
import mne
import numpy as np

from .output import PreprocessedEEGOutput
from .types import PreprocessingConfig


def _load_raw_eeg(path: str) -> mne.io.BaseRaw:
    """Load raw EEG data from various supported file formats.

    Args:
        path: Path to the raw EEG data file.

    Returns:
        Loaded mne.io.BaseRaw instance with data preloaded.
    """
    lower = path.lower()
    if lower.endswith((".fif", ".fif.gz")):
        return mne.io.read_raw_fif(path, preload=True, verbose=False)
    elif lower.endswith(".mff"):
        return mne.io.read_raw_egi(path, preload=True, verbose=False)
    elif lower.endswith(".vhdr"):
        return mne.io.read_raw_brainvision(path, preload=True, verbose=False)
    elif lower.endswith(".edf"):
        return mne.io.read_raw_edf(path, preload=True, verbose=False)
    elif lower.endswith(".bdf"):
        return mne.io.read_raw_bdf(path, preload=True, verbose=False)
    elif lower.endswith(".set"):
        return mne.io.read_raw_eeglab(path, preload=True, verbose=False)
    else:
        return mne.io.read_raw(path, preload=True, verbose=False)


def run_preprocessing(
    config: PreprocessingConfig,
    raw: Optional[mne.io.BaseRaw] = None
) -> PreprocessedEEGOutput:
    """Run preprocessing pipeline on raw EEG data.

    Processing sequence:
    1. Load raw data if not directly provided in memory.
    2. Resample to target sampling rate (e.g. 125 Hz).
    3. Apply zero-phase FIR bandpass filter (e.g. 1.0 - 50.0 Hz).
    4. Detect bad channels via PREP / NoisyChannels, interpolate them, and apply average reference.
    5. Fit FastICA and identify/remove artifact components (e.g. EOG).

    Args:
        config: Preprocessing configuration parameters.
        raw: Optional in-memory BaseRaw instance (primarily for testing).

    Returns:
        PreprocessedEEGOutput containing clean BaseRaw and metadata.
    """
    if raw is None:
        raw = _load_raw_eeg(config.raw_eeg_path)
    else:
        raw = raw.copy()

    if not raw.preload:
        raw.load_data()

    # 1. Resampling
    if raw.info["sfreq"] > config.target_sampling_rate:
        raw.resample(sfreq=config.target_sampling_rate, npad="auto", verbose=False)

    # 2. Bandpass filtering
    raw.filter(
        l_freq=config.l_freq,
        h_freq=config.h_freq,
        phase="zero",
        fir_design="firwin",
        verbose=False
    )

    # 3. PREP pipeline for bad channel detection and robust re-referencing
    bad_channels: List[str] = []
    if config.apply_prep:
        montage = raw.get_montage()
        eeg_picks = mne.pick_types(raw.info, meg=False, eeg=True, eog=False)
        eeg_chs = [raw.ch_names[i] for i in eeg_picks] if len(eeg_picks) > 0 else raw.ch_names

        if montage is not None and len(eeg_chs) >= 4:
            try:
                from pyprep.prep_pipeline import PrepPipeline

                nyquist = raw.info["sfreq"] / 2.0
                line_freqs = np.arange(50, nyquist, 50)
                prep_params = {
                    "ref_chs": eeg_chs,
                    "reref_chs": eeg_chs,
                    "line_freqs": line_freqs,
                }
                prep = PrepPipeline(
                    raw.copy(),
                    prep_params,
                    montage,
                    random_state=config.random_state,
                    ransac=False
                )
                prep.fit()
                bad_channels = list(prep.noisy_channels_original.get("bad_all", []))
            except Exception:
                try:
                    from pyprep.find_noisy_channels import NoisyChannels

                    nd = NoisyChannels(raw.copy(), random_state=config.random_state)
                    nd.find_all_bads(ransac=False)
                    bad_channels = list(nd.get_bads())
                except Exception:
                    bad_channels = list(raw.info.get("bads", []))
        else:
            bad_channels = list(raw.info.get("bads", []))

        if bad_channels:
            raw.info["bads"] = bad_channels
            if raw.get_montage() is not None:
                try:
                    raw.interpolate_bads(reset_bads=True, mode="accurate", verbose=False)
                except Exception:
                    pass

        try:
            raw.set_eeg_reference("average", projection=False, verbose=False)
        except Exception:
            pass

    # 4. FastICA artifact removal
    removed_ica_components: List[int] = []
    eeg_picks = mne.pick_types(raw.info, meg=False, eeg=True, eog=False)
    n_channels = len(eeg_picks) if len(eeg_picks) > 0 else len(raw.ch_names)
    n_components = min(config.ica_n_components, n_channels)

    if n_components > 1:
        try:
            ica = mne.preprocessing.ICA(
                n_components=n_components,
                method="fastica",
                random_state=config.random_state,
                max_iter=800
            )
            ica.fit(raw, verbose=False)

            eog_picks = mne.pick_types(raw.info, meg=False, eeg=False, eog=True)
            eog_inds: List[int] = []
            if len(eog_picks) > 0:
                eog_inds, _ = ica.find_bads_eog(raw, verbose=False)
            else:
                for candidate in ["Fp1", "Fp2", "FP1", "FP2", "E1", "E8"]:
                    if candidate in raw.ch_names:
                        try:
                            inds, _ = ica.find_bads_eog(raw, ch_name=candidate, verbose=False)
                            eog_inds.extend(inds)
                        except Exception:
                            pass
                        break

            removed_ica_components = sorted(list(set(eog_inds)))
            if removed_ica_components:
                ica.exclude = removed_ica_components
                raw = ica.apply(raw.copy(), verbose=False)
        except Exception:
            pass

    return PreprocessedEEGOutput(
        raw=raw,
        sampling_rate=float(raw.info["sfreq"]),
        bad_channels=bad_channels,
        removed_ica_components=removed_ica_components
    )
