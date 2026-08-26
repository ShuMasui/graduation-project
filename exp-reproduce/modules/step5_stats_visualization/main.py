"""
Step 5: Statistical Testing & Visualization Module.

Performs vectorized paired permutation tests between experimental conditions
(e.g., Rest vs Video) across CerebrA cortical parcels, evaluates significance,
generates publication-ready statistical summary plots, and renders 8-view
cortical surface activation maps.
"""
import os
import logging
from typing import List, Optional, Tuple, Any
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
import pandas as pd
import seaborn as sns
import mne

from .output import StatsVisualizationOutput
from .types import StatsVizConfig

logger = logging.getLogger(__name__)


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
    fig.savefig(fig_boxplot_path, dpi=config.dpi)
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

    ax.bar(
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
    fig.savefig(fig_barplot_path, dpi=config.dpi)
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
    fig.savefig(fig_pval_path, dpi=config.dpi)
    plt.close(fig)
    figure_paths.append(fig_pval_path)

    return figure_paths


def _load_surface_mesh(
    src_out: Any,
    subjects_dir: Optional[str] = None,
    subject_name: Optional[str] = None
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load LH and RH surface coordinates and triangle topologies.

    Priority:
    1. FreeSurfer inflated surface meshes (`surf/lh.inflated`, `surf/rh.inflated`).
    2. Fallback to `src[0]['rr']`, `src[1]['rr']` and source space triangulation.

    Parameters:
        src_out: AtlasSourceOutput containing SourceSpaces.
        subjects_dir: Optional FreeSurfer subjects directory.
        subject_name: Optional subject identifier (default: 'icbm152').

    Returns:
        Tuple of (coords_lh, tris_lh, coords_rh, tris_rh).
    """
    subj_name = subject_name or "icbm152"
    candidate_dirs = []
    if subjects_dir:
        candidate_dirs.append(os.path.join(subjects_dir, subj_name, "surf"))
        candidate_dirs.append(os.path.join(subjects_dir, "surf"))
        candidate_dirs.append(subjects_dir)

    # Standard candidate paths in repo
    candidate_dirs.extend([
        os.path.join("exp-reproduce", "subjects", subj_name, "surf"),
        os.path.join("subjects", subj_name, "surf"),
        os.path.join("exp-reproduce", "subjects", "surf"),
        os.path.join("subjects", "surf"),
    ])

    lh_inflated_path = None
    rh_inflated_path = None
    for c_dir in candidate_dirs:
        lh_p = os.path.join(c_dir, "lh.inflated")
        rh_p = os.path.join(c_dir, "rh.inflated")
        if os.path.exists(lh_p) and os.path.exists(rh_p):
            lh_inflated_path = lh_p
            rh_inflated_path = rh_p
            break

    coords_lh = None
    coords_rh = None
    faces_lh = None
    faces_rh = None

    if lh_inflated_path and rh_inflated_path:
        try:
            coords_lh, faces_lh = mne.read_surface(lh_inflated_path)
            coords_rh, faces_rh = mne.read_surface(rh_inflated_path)
        except Exception as e:
            logger.warning("Failed to read FreeSurfer inflated surfaces: %s. Using fallback.", e)
            coords_lh, coords_rh = None, None

    # Fallback to source space rr coordinates if inflated surface not found
    src = getattr(src_out, "src", None)
    if coords_lh is None or coords_rh is None:
        if src is not None and len(src) >= 1 and "rr" in src[0]:
            coords_lh = np.array(src[0]["rr"], dtype=float)
            if coords_lh.size > 0 and np.max(np.abs(coords_lh)) < 1.0:
                coords_lh = coords_lh * 1000.0
        else:
            coords_lh = np.zeros((1, 3), dtype=float)

        if src is not None and len(src) >= 2 and "rr" in src[1]:
            coords_rh = np.array(src[1]["rr"], dtype=float)
            if coords_rh.size > 0 and np.max(np.abs(coords_rh)) < 1.0:
                coords_rh = coords_rh * 1000.0
        else:
            coords_rh = np.zeros((1, 3), dtype=float)

    # Resolve triangle topology for LH
    tris_lh = None
    if src is not None and len(src) >= 1:
        if src[0].get("use_tris") is not None and len(src[0]["use_tris"]) > 0:
            tris_lh = np.array(src[0]["use_tris"], dtype=int)
        elif src[0].get("tris") is not None and len(src[0]["tris"]) > 0:
            tris_lh = np.array(src[0]["tris"], dtype=int)

    if tris_lh is None and faces_lh is not None and len(faces_lh) > 0:
        tris_lh = np.array(faces_lh, dtype=int)
    elif tris_lh is None:
        if len(coords_lh) >= 3:
            tris_lh = np.array([[0, 1, 2]], dtype=int)
        else:
            tris_lh = np.zeros((0, 3), dtype=int)

    # Resolve triangle topology for RH
    tris_rh = None
    if src is not None and len(src) >= 2:
        if src[1].get("use_tris") is not None and len(src[1]["use_tris"]) > 0:
            tris_rh = np.array(src[1]["use_tris"], dtype=int)
        elif src[1].get("tris") is not None and len(src[1]["tris"]) > 0:
            tris_rh = np.array(src[1]["tris"], dtype=int)

    if tris_rh is None and faces_rh is not None and len(faces_rh) > 0:
        tris_rh = np.array(faces_rh, dtype=int)
    elif tris_rh is None:
        if len(coords_rh) >= 3:
            tris_rh = np.array([[0, 1, 2]], dtype=int)
        else:
            tris_rh = np.zeros((0, 3), dtype=int)

    return coords_lh, tris_lh, coords_rh, tris_rh


def _map_labels_to_triangles(
    cerebra_labels: List[mne.Label],
    sub_df: pd.DataFrame,
    coords_lh: np.ndarray,
    tris_lh: np.ndarray,
    coords_rh: np.ndarray,
    tris_rh: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Map parcel MRA values to surface vertices and compute mean values per triangle face.

    Parameters:
        cerebra_labels: List of CerebrA Label objects.
        sub_df: DataFrame containing 'region_name' and 'mean_activation_na_m'.
        coords_lh: LH vertex coordinates.
        tris_lh: LH triangle vertex index array.
        coords_rh: RH vertex coordinates.
        tris_rh: RH triangle vertex index array.

    Returns:
        Tuple of (tri_vals_lh, tri_vals_rh).
    """
    mra_map = dict(zip(sub_df["region_name"], sub_df["mean_activation_na_m"]))

    v_vals_lh = np.zeros(len(coords_lh), dtype=float)
    v_vals_rh = np.zeros(len(coords_rh), dtype=float)

    for lbl in cerebra_labels:
        if lbl.name not in mra_map:
            continue
        val = mra_map[lbl.name]
        verts = np.asarray(lbl.vertices, dtype=int)
        if lbl.hemi == "lh":
            valid = verts[verts < len(v_vals_lh)]
            v_vals_lh[valid] = val
        elif lbl.hemi == "rh":
            valid = verts[verts < len(v_vals_rh)]
            v_vals_rh[valid] = val

    # LH Triangle values
    if len(tris_lh) > 0 and tris_lh.max() < len(v_vals_lh):
        tri_vals_lh = np.mean(v_vals_lh[tris_lh], axis=1)
    elif len(tris_lh) > 0:
        tri_vals_lh = np.zeros(len(tris_lh), dtype=float)
    else:
        tri_vals_lh = np.empty(0, dtype=float)

    # RH Triangle values
    if len(tris_rh) > 0 and tris_rh.max() < len(v_vals_rh):
        tri_vals_rh = np.mean(v_vals_rh[tris_rh], axis=1)
    elif len(tris_rh) > 0:
        tri_vals_rh = np.zeros(len(tris_rh), dtype=float)
    else:
        tri_vals_rh = np.empty(0, dtype=float)

    return tri_vals_lh, tri_vals_rh


def plot_brain_8views(
    all_subjects_mra_df: pd.DataFrame,
    src_out: Any,
    output_dir: str = "./results",
    subjects_dir: Optional[str] = None,
    subject_name: Optional[str] = "icbm152",
    brain_maps_dir: Optional[str] = None,
    dpi: int = 300
) -> List[str]:
    """Generate 8-view cortical activation maps for each subject and condition.

    Views layout (2x4 grid):
    Row 1: Anterior, Posterior, Superior, Inferior
    Row 2: Left Lateral, Right Lateral, Left Medial, Right Medial

    Parameters:
        all_subjects_mra_df: DataFrame containing regional activations for subjects.
        src_out: AtlasSourceOutput containing SourceSpaces and cerebra_labels.
        output_dir: Base output directory.
        subjects_dir: Optional FreeSurfer subjects directory.
        subject_name: Optional subject identifier (default: 'icbm152').
        brain_maps_dir: Optional custom destination directory for brain maps.
        dpi: Output image resolution (default: 300).

    Returns:
        List of generated figure paths.
    """
    if all_subjects_mra_df.empty:
        return []

    target_dir = brain_maps_dir or os.path.join(output_dir, "brain_maps")
    os.makedirs(target_dir, exist_ok=True)

    # 1. Load surface meshes
    coords_lh, tris_lh, coords_rh, tris_rh = _load_surface_mesh(
        src_out, subjects_dir=subjects_dir, subject_name=subject_name
    )

    if len(tris_lh) > 0 and tris_lh.max() < len(coords_lh):
        mesh_lh = coords_lh[tris_lh]
    else:
        mesh_lh = np.empty((0, 3, 3), dtype=float)

    if len(tris_rh) > 0 and tris_rh.max() < len(coords_rh):
        mesh_rh = coords_rh[tris_rh]
    else:
        mesh_rh = np.empty((0, 3, 3), dtype=float)

    all_coords = np.vstack([coords_lh, coords_rh])

    # 2. Unified colormap scaling across entire dataset
    vmin = float(all_subjects_mra_df["mean_activation_na_m"].min())
    vmax = float(all_subjects_mra_df["mean_activation_na_m"].max())
    if vmin == vmax:
        vmin -= 0.1
        vmax += 0.1

    norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.get_cmap("viridis")

    # 3. 8 Standard Views configuration:
    # (title, elevation, azimuth, hemispheres_to_draw, primary_view_axis)
    views = [
        ("1. Anterior", 0, 90, ["lh", "rh"], "Y"),
        ("2. Posterior", 0, -90, ["lh", "rh"], "Y"),
        ("3. Superior", 90, -90, ["lh", "rh"], "Z"),
        ("4. Inferior", -90, -90, ["lh", "rh"], "Z"),
        ("5. Left Lateral", 0, 180, ["lh"], "X"),
        ("6. Right Lateral", 0, 0, ["rh"], "X"),
        ("7. Left Medial", 0, 0, ["lh"], "X"),
        ("8. Right Medial", 0, 180, ["rh"], "X"),
    ]

    saved_paths: List[str] = []
    cerebra_labels = getattr(src_out, "cerebra_labels", [])

    # 4. Group by (subject_id, condition) and render
    grouped = all_subjects_mra_df.groupby(["subject_id", "condition"], sort=True)

    for (sub_id, cond_name), group_df in grouped:
        tri_vals_lh, tri_vals_rh = _map_labels_to_triangles(
            cerebra_labels, group_df, coords_lh, tris_lh, coords_rh, tris_rh
        )

        fc_lh = cmap(norm(tri_vals_lh)) if len(tri_vals_lh) > 0 else np.empty((0, 4))
        fc_rh = cmap(norm(tri_vals_rh)) if len(tri_vals_rh) > 0 else np.empty((0, 4))

        fig, axes = plt.subplots(2, 4, figsize=(18, 9), subplot_kw={"projection": "3d"})
        axes_flat = axes.flatten()

        for idx, (title, elev, azim, hemis, view_axis) in enumerate(views):
            ax = axes_flat[idx]

            # Determine coordinates subset for tight aspect box
            if hemis == ["lh"] and len(coords_lh) > 0:
                sub_coords = coords_lh
            elif hemis == ["rh"] and len(coords_rh) > 0:
                sub_coords = coords_rh
            else:
                sub_coords = all_coords

            sub_center = np.mean(sub_coords, axis=0) if len(sub_coords) > 0 else np.zeros(3)
            ptp = np.ptp(sub_coords, axis=0) if len(sub_coords) > 0 else np.ones(3)

            if view_axis == "X":
                vis_max = max(ptp[1], ptp[2])
            elif view_axis == "Y":
                vis_max = max(ptp[0], ptp[2])
            else:  # "Z"
                vis_max = max(ptp[0], ptp[1])

            r = max((vis_max / 2.0) * 0.95, 1.0)

            if "lh" in hemis and len(mesh_lh) > 0 and len(fc_lh) == len(mesh_lh):
                poly_lh = Poly3DCollection(mesh_lh, facecolors=fc_lh, shade=True, alpha=1.0)
                poly_lh.set_edgecolor("none")
                ax.add_collection3d(poly_lh)

            if "rh" in hemis and len(mesh_rh) > 0 and len(fc_rh) == len(mesh_rh):
                poly_rh = Poly3DCollection(mesh_rh, facecolors=fc_rh, shade=True, alpha=1.0)
                poly_rh.set_edgecolor("none")
                ax.add_collection3d(poly_rh)

            ax.set_xlim(sub_center[0] - r, sub_center[0] + r)
            ax.set_ylim(sub_center[1] - r, sub_center[1] + r)
            ax.set_zlim(sub_center[2] - r, sub_center[2] + r)
            ax.view_init(elev=elev, azim=azim)
            ax.set_box_aspect((1, 1, 1))
            ax.axis("off")
            ax.set_title(title, fontsize=13, fontweight="bold", pad=-5)

        fig.subplots_adjust(
            left=0.02, right=0.98, bottom=0.12, top=0.92, wspace=0.02, hspace=0.08
        )

        # Unified horizontal colorbar
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar_ax = fig.add_axes([0.25, 0.05, 0.50, 0.03])
        cbar = fig.colorbar(sm, cax=cbar_ax, orientation="horizontal")
        cbar.set_label(
            "Mean Regional Activation (MRA, nA/m)",
            fontsize=12,
            fontweight="bold",
            labelpad=6
        )
        cbar.ax.tick_params(labelsize=10)

        fig.suptitle(
            f"CerebrA Cortical Activation Map (8 Views) - Subject: {sub_id} | Condition: {cond_name}",
            fontsize=15,
            fontweight="bold",
            y=0.98
        )

        fig_path = os.path.join(target_dir, f"{sub_id}_{cond_name}_8views.png")
        fig.savefig(fig_path, dpi=dpi)
        plt.close(fig)
        saved_paths.append(fig_path)

    return saved_paths


def run_stats_visualization(
    all_subjects_mra_df: pd.DataFrame,
    config: StatsVizConfig,
    src_out: Optional[Any] = None
) -> StatsVisualizationOutput:
    """Execute vectorized paired permutation test and generate visualization figures.

    Parameters:
        all_subjects_mra_df: DataFrame containing regional activations for all subjects.
                             Required columns: ['subject_id', 'condition', 'region_name', 'mean_activation_na_m']
        config: Statistical testing and plotting configuration.
        src_out: Optional AtlasSourceOutput for generating 8-view cortical brain maps.

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

    # 5. Generate statistical plots
    figure_paths = _generate_plots(df_paired, stats_df, config)

    # 6. Generate 8-view brain maps if src_out is available
    effective_src_out = src_out if src_out is not None else config.src_out
    if effective_src_out is not None:
        brain_map_paths = plot_brain_8views(
            all_subjects_mra_df=df_paired,
            src_out=effective_src_out,
            output_dir=config.output_dir,
            subjects_dir=config.subjects_dir,
            subject_name=config.subject_name,
            brain_maps_dir=config.brain_maps_dir,
            dpi=config.dpi
        )
        figure_paths.extend(brain_map_paths)

    return StatsVisualizationOutput(
        stats_df=stats_df,
        figure_paths=figure_paths,
        output_dir=config.output_dir
    )

