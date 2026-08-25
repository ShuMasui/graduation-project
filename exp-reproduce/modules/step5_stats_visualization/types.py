"""Configuration and internal types for Step 5 (Stats & Visualization)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StatsVizConfig:
    """Configuration for statistical testing and visualization.

    Attributes:
        condition_a: Baseline condition name (e.g. 'rest').
        condition_b: Comparison condition name (e.g. 'video1').
        n_permutations: Number of permutation iterations (default: 10000).
        p_threshold: Significance threshold alpha (default: 0.05).
        output_dir: Directory where results and plots are saved (default: './results').
        random_state: Random seed for permutation test reproducibility (default: 42).
    """
    condition_a: str
    condition_b: str
    n_permutations: int = 10000
    p_threshold: float = 0.05
    output_dir: str = "./results"
    random_state: int = 42
