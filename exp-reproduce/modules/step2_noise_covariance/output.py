"""Output data contract for Step 2 noise covariance."""

from dataclasses import dataclass
import mne


@dataclass(frozen=True)
class CovarianceLambdaOutput:
    """Noise covariance and dynamic lambda2 output DTO."""

    noise_cov: mne.Covariance
    snr_db: float
    lambda2: float
