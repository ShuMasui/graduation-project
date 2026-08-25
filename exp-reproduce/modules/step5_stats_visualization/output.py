"""Output contract for Step 5 (Stats & Visualization)."""
from dataclasses import dataclass
from typing import List
import pandas as pd


@dataclass(frozen=True)
class StatsVisualizationOutput:
    """Step 5 output contract.

    Attributes:
        stats_df: Statistical results DataFrame with columns:
                  ['region_name', 'mean_a', 'mean_b', 'mean_diff', 'p_value', 'significant'].
        figure_paths: List of saved figure file paths.
        output_dir: Output directory where results and figures were saved.
    """
    stats_df: pd.DataFrame
    figure_paths: List[str]
    output_dir: str
