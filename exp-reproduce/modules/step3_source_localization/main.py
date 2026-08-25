"""Step 3: eLORETA Source localization solver."""

from typing import Optional
import mne

from modules.step0c_forward_model.output import ForwardModelOutput
from modules.step1_preprocessing.output import PreprocessedEEGOutput
from modules.step2_noise_covariance.output import CovarianceLambdaOutput
from .output import SourceEstimateOutput
from .types import SourceLocConfig


def run_source_localization(
    fwd_out: ForwardModelOutput,
    eeg_out: PreprocessedEEGOutput,
    cov_out: CovarianceLambdaOutput,
    config: Optional[SourceLocConfig] = None
) -> SourceEstimateOutput:
    """Compute brain source current density estimates using eLORETA.

    Args:
        fwd_out: Forward model output from Step 0-C.
        eeg_out: Preprocessed EEG data from Step 1.
        cov_out: Noise covariance and lambda2 from Step 2.
        config: Optional source localization configuration.

    Returns:
        SourceEstimateOutput containing the estimated mne.SourceEstimate (stc) in nA/m.
    """
    if config is None:
        config = SourceLocConfig()

    raw = eeg_out.raw
    forward = fwd_out.forward
    noise_cov = cov_out.noise_cov
    lambda2 = cov_out.lambda2

    # 1. Construct inverse operator
    inv_op = mne.minimum_norm.make_inverse_operator(
        info=raw.info,
        forward=forward,
        noise_cov=noise_cov,
        loose=config.loose,
        depth=config.depth,
        fixed=False,
        verbose=False
    )

    # 2. Solve inverse problem with eLORETA
    stc = mne.minimum_norm.apply_inverse_raw(
        raw=raw,
        inverse_operator=inv_op,
        lambda2=lambda2,
        method=config.method,
        pick_ori=config.pick_ori,
        prepared=config.prepared,
        verbose=False
    )

    return SourceEstimateOutput(
        stc=stc,
        method=config.method,
        lambda2_used=lambda2
    )
