"""Output contract for Step 4 (CerebrA Parcellation / MRA)."""
from dataclasses import dataclass
from typing import List
import pandas as pd


@dataclass(frozen=True)
class RegionalActivationOutput:
    """Mean Regional Activation (MRA) output contract.

    Attributes:
        mra_df: DataFrame with columns ['subject_id', 'condition', 'region_name', 'mean_activation_na_m'].
        region_names: List of all cortical region names (62 regions).
    """
    mra_df: pd.DataFrame
    region_names: List[str]
