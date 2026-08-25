"""Step 2: Noise covariance estimation and dynamic lambda2 calculation."""

from typing import Optional
import mne
import numpy as np

from modules.step1_preprocessing.output import PreprocessedEEGOutput
from .output import CovarianceLambdaOutput
from .types import NoiseCovConfig


def run_noise_covariance(
    eeg_out: PreprocessedEEGOutput,
    config: Optional[NoiseCovConfig] = None
) -> CovarianceLambdaOutput:
    """Compute noise covariance matrix and derive dynamic regularization parameter lambda^2.

    Mathematical Formulation:
    1. Instantaneous signal power across N_ch channels at sample time t:
       p(t) = (1 / N_ch) * sum_{i=1}^{N_ch} X_{i,t}^2
    2. Mean power P = mean(p(t)), and variance sigma^2 = var(p(t))
    3. Signal-to-Noise Ratio (SNR) in dB:
       SNR = 10 * log10(P / sigma^2)
    4. Regularization parameter lambda^2:
       lambda^2 = 1 / SNR^2

    Args:
        eeg_out: Preprocessed EEG data from Step 1.
        config: Optional noise covariance configuration.

    Returns:
        CovarianceLambdaOutput containing regularized noise_cov, snr_db, and lambda2.
    """
    if config is None:
        config = NoiseCovConfig()

    raw = eeg_out.raw

    # 1. Compute empirical noise covariance and regularize
    cov = mne.compute_raw_covariance(
        raw,
        tmin=config.tmin,
        tmax=config.tmax,
        method=config.method,
        verbose=False
    )
    cov = mne.cov.regularize(cov, raw.info, rank=None, proj=True, verbose=False)

    # 2. Extract data slice for power calculation
    sfreq = float(raw.info["sfreq"])
    start_idx = int(config.tmin * sfreq) if config.tmin is not None else 0
    stop_idx = int(config.tmax * sfreq) if config.tmax is not None else None

    data = raw.get_data(start=start_idx, stop=stop_idx)

    # 3. Vectorized signal power, SNR, and lambda2 computation
    signal_power = np.mean(data ** 2, axis=0)  # Shape: (n_times,)
    p_mean = float(np.mean(signal_power))
    sigma2 = float(np.var(signal_power))

    if sigma2 <= 0.0 or p_mean <= 0.0:
        snr_db = 1.0
        lambda2 = 1.0
    else:
        ratio = p_mean / sigma2
        if ratio <= 1.0:
            snr_db = 1.0
            lambda2 = 1.0
        else:
            snr_db = float(10.0 * np.log10(ratio))
            lambda2 = float(1.0 / (snr_db ** 2)) if snr_db > 0 else 1.0

    return CovarianceLambdaOutput(
        noise_cov=cov,
        snr_db=snr_db,
        lambda2=lambda2
    )
