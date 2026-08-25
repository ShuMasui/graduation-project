"""
Step 5: Statistical Testing & Visualization Module.

Performs vectorized paired permutation tests between experimental conditions
(e.g., Rest vs Video) across CerebrA cortical parcels, evaluates significance,
and generates publication-ready statistical summary plots.
"""
import os
from typing import List
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .output import StatsVisualizationOutput
from .types import StatsVizConfig


def _generate_plots(
    df_filtered: pd.DataFrame,
    stats_df: pd.DataFrame,
    config: StatsVizConfig
) -> List[str]:
    """Generate statistical visualization figures and save to disk.

    Parameters:
        df_filtered: Long-form DataFrame filtered to conditions A and B.
        stats_df: Statistical results DataFrame.
        config: Visualization configuration.

    Returns:
        List of saved figure paths.
    """
    figure_paths: List[str] = []

    # 1. Condition Comparison Boxplot / Distribution (Figure 4 analogue)
    fig_boxplot_path = os.path.join(config.output_dir, "condition_comparison_boxplot.png")
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.boxplot(
        data=df_filtered,
        x="condition",
        y="mean_activation_na_m",
        hue="condition",
        palette="Set2",
        legend=False,
        ax=ax
    )
    sns.stripplot(
        data=df_filtered,
        x="condition",
        y="mean_activation_na_m",
        color="black",
        alpha=0.6,
        jitter=0.2,
        size=5,
        ax=ax
    )
    ax.set_title(
        f"Mean Regional Activation: {config.condition_a} vs {config.condition_b}",
        fontsize=14,
        fontweight="bold"
    )
    ax.set_xlabel("Condition", fontsize=12)
    ax.set_ylabel("MRA (nA/m)", fontsize=12)
    fig.tight_layout()
    fig.savefig(fig_boxplot_path, dpi=300)
    plt.close(fig)
    figure_paths.append(fig_boxplot_path)

    # 2. Regional MRA Difference Bar Plot with Significance Highlight
    fig_barplot_path = os.path.join(config.output_dir, "mra_difference_barplot.png")
    fig, ax = plt.subplots(figsize=(16, 8))

    colors = [
        "#d95f02" if sig else "#7570b3" if diff < 0 else "#1b9e77"
        for sig, diff in zip(stats_df["significant"], stats_df["mean_diff"])
    ]
    # Highlight non-significant regions with lighter color
    colors = [
        c if sig else "#bdbdbd"
        for c, sig in zip(colors, stats_df["significant"])
    ]

    bars = ax.bar(
        range(len(stats_df)),
        stats_df["mean_diff"],
        color=colors,
        edgecolor="black",
        linewidth=0.5
    )

    ax.axhline(0, color="black", linestyle="--", linewidth=0.8)
    ax.set_xticks(range(len(stats_df)))
    ax.set_xticklabels(
        stats_df["region_name"],
        rotation=90,
        fontsize=7,
        ha="right"
    )
    ax.set_title(
        f"Regional Activation Differences ({config.condition_b} - {config.condition_a}) "
        f"[Highlighted: p < {config.p_threshold}]",
        fontsize=14,
        fontweight="bold"
    )
    ax.set_xlabel("CerebrA Cortical Region", fontsize=12)
    ax.set_ylabel(r"$\Delta$ MRA (nA/m)", fontsize=12)
    fig.tight_layout()
    fig.savefig(fig_barplot_path, dpi=300)
    plt.close(fig)
    figure_paths.append(fig_barplot_path)

    # 3. Permutation P-value Distribution Histogram
    fig_pval_path = os.path.join(config.output_dir, "p_value_distribution.png")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(
        stats_df["p_value"],
        bins=np.linspace(0, 1, 21),
        color="#386cb0",
        edgecolor="white"
    )
    ax.axvline(
        config.p_threshold,
        color="red",
        linestyle="--",
        linewidth=1.5,
        label=f"Threshold (p = {config.p_threshold})"
    )
    ax.set_title("Permutation Test P-Value Distribution Across Regions", fontsize=12)
    ax.set_xlabel("p-value", fontsize=10)
    ax.set_ylabel("Number of Regions", fontsize=10)
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_pval_path, dpi=300)
    plt.close(fig)
    figure_paths.append(fig_pval_path)

    return figure_paths


def run_stats_visualization(
    all_subjects_mra_df: pd.DataFrame,
    config: StatsVizConfig
) -> StatsVisualizationOutput:
    """Execute vectorized paired permutation test and generate visualization figures.

    Parameters:
        all_subjects_mra_df: DataFrame containing regional activations for all subjects.
                             Required columns: ['subject_id', 'condition', 'region_name', 'mean_activation_na_m']
        config: Statistical testing and plotting configuration.

    Returns:
        StatsVisualizationOutput containing statistical table, figure paths, and output dir.

    Raises:
        ValueError: If required columns are missing, conditions are not found, or no
                    overlapping paired subjects are available.
    """
    required_cols = {"subject_id", "condition", "region_name", "mean_activation_na_m"}
    missing_cols = required_cols - set(all_subjects_mra_df.columns)
    if missing_cols:
        raise ValueError(f"Input DataFrame is missing required columns: {missing_cols}")

    # 1. Filter to target conditions
    df_filtered = all_subjects_mra_df[
        all_subjects_mra_df["condition"].isin([config.condition_a, config.condition_b])
    ].copy()

    if df_filtered.empty:
        raise ValueError(
            f"No records found for conditions '{config.condition_a}' "
            f"or '{config.condition_b}'."
        )

    # 2. Extract paired subjects having data in BOTH conditions
    subjects_a = set(
        df_filtered[df_filtered["condition"] == config.condition_a]["subject_id"]
    )
    subjects_b = set(
        df_filtered[df_filtered["condition"] == config.condition_b]["subject_id"]
    )
    common_subjects = sorted(list(subjects_a.intersection(subjects_b)))

    if not common_subjects:
        raise ValueError(
            f"No paired subjects found with records in both '{config.condition_a}' "
            f"and '{config.condition_b}'."
        )

    # Preserve consistent region ordering
    region_names: List[str] = list(
        df_filtered[df_filtered["condition"] == config.condition_a]["region_name"].unique()
    )

    # Pivot to construct paired matrices (subject_id x region_name)
    df_paired = df_filtered[df_filtered["subject_id"].isin(common_subjects)]
    pivot_a = df_paired[df_paired["condition"] == config.condition_a].pivot(
        index="subject_id",
        columns="region_name",
        values="mean_activation_na_m"
    ).reindex(index=common_subjects, columns=region_names)

    pivot_b = df_paired[df_paired["condition"] == config.condition_b].pivot(
        index="subject_id",
        columns="region_name",
        values="mean_activation_na_m"
    ).reindex(index=common_subjects, columns=region_names)

    mat_a = pivot_a.to_numpy()  # shape: (n_subjects, n_regions)
    mat_b = pivot_b.to_numpy()  # shape: (n_subjects, n_regions)

    if np.isnan(mat_a).any() or np.isnan(mat_b).any():
        raise ValueError("Paired condition matrices contain NaN values across subjects.")

    # 3. Vectorized Paired Permutation Test
    # Difference matrix D = X_B - X_A (shape: n_subjects, n_regions)
    diff_matrix = mat_b - mat_a
    n_subjects, n_regions = diff_matrix.shape

    # Observed mean difference: shape (n_regions,)
    observed_diff = np.mean(diff_matrix, axis=0)

    # Generate random signs matrix: shape (n_permutations, n_subjects, 1) with values in {-1, +1}
    rng = np.random.default_rng(config.random_state)
    signs = rng.choice([-1.0, 1.0], size=(config.n_permutations, n_subjects, 1))

    # Broadcast multiplication and vectorized mean across subjects (axis=1)
    # diff_matrix[np.newaxis, :, :] has shape (1, n_subjects, n_regions)
    # Product shape: (n_permutations, n_subjects, n_regions)
    # perm_diffs shape: (n_permutations, n_regions)
    perm_diffs = np.mean(signs * diff_matrix[np.newaxis, :, :], axis=1)

    # Two-sided p-value vectorization across permutations (axis=0)
    p_values = np.mean(np.abs(perm_diffs) >= np.abs(observed_diff), axis=0)

    # 4. Assemble Statistical Results DataFrame
    mean_a = np.mean(mat_a, axis=0)
    mean_b = np.mean(mat_b, axis=0)
    significant = p_values < config.p_threshold

    stats_df = pd.DataFrame({
        "region_name": region_names,
        "mean_a": mean_a,
        "mean_b": mean_b,
        "mean_diff": observed_diff,
        "p_value": p_values,
        "significant": significant
    })

    # Ensure output directory exists and save CSV
    os.makedirs(config.output_dir, exist_ok=True)
    csv_path = os.path.join(config.output_dir, "permutation_test_results.csv")
    stats_df.to_csv(csv_path, index=False)

    # 5. Generate and save publication plots
    figure_paths = _generate_plots(df_paired, stats_df, config)

    return StatsVisualizationOutput(
        stats_df=stats_df,
        figure_paths=figure_paths,
        output_dir=config.output_dir
    )
