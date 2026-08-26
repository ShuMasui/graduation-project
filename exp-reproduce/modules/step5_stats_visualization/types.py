from dataclasses import dataclass
from typing import Optional, Any


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
        subjects_dir: Optional FreeSurfer subjects directory for 3D inflated surfaces.
        subject_name: Optional FreeSurfer subject name (default: 'icbm152').
        brain_maps_dir: Optional custom directory for 8-view brain maps.
        src_out: Optional AtlasSourceOutput for cortical mesh and CerebrA labels.
        dpi: DPI resolution for output figures (default: 300).
    """
    condition_a: str
    condition_b: str
    n_permutations: int = 10000
    p_threshold: float = 0.05
    output_dir: str = "./results"
    random_state: int = 42
    subjects_dir: Optional[str] = None
    subject_name: Optional[str] = "icbm152"
    brain_maps_dir: Optional[str] = None
    src_out: Optional[Any] = None
    dpi: int = 300

