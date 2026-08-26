import os
import shutil
import tempfile
import unittest
import mne
import numpy as np
import pandas as pd

from modules.step0b_atlas_source.output import AtlasSourceOutput
from modules.step5_stats_visualization.main import (
    run_stats_visualization,
    plot_brain_8views,
    _load_surface_mesh,
    _map_labels_to_triangles
)
from modules.step5_stats_visualization.output import StatsVisualizationOutput
from modules.step5_stats_visualization.types import StatsVizConfig


def _generate_synthetic_mra_df(
    n_subjects: int = 10,
    n_regions: int = 62,
    n_significant: int = 5,
    random_state: int = 42
) -> pd.DataFrame:
    """Helper to create synthetic MRA DataFrame for conditions A and B."""
    rng = np.random.default_rng(random_state)
    records = []
    region_names = [f"CerebrA_Region_{i+1:02d}" for i in range(n_regions)]

    for sub_idx in range(n_subjects):
        sub_id = f"sub-{sub_idx+1:02d}"

        # Baseline condition A (e.g. rest): mean ~ 5.0
        val_a = rng.normal(loc=5.0, scale=0.5, size=n_regions)
        for r_name, v in zip(region_names, val_a):
            records.append({
                "subject_id": sub_id,
                "condition": "rest",
                "region_name": r_name,
                "mean_activation_na_m": float(v)
            })

        # Comparison condition B (e.g. video1):
        # First `n_significant` regions have large positive shift
        val_b = rng.normal(loc=5.0, scale=0.5, size=n_regions)
        val_b[:n_significant] += 4.0  # Clear effect
        for r_name, v in zip(region_names, val_b):
            records.append({
                "subject_id": sub_id,
                "condition": "video1",
                "region_name": r_name,
                "mean_activation_na_m": float(v)
            })

    return pd.DataFrame(records)


def _create_synthetic_src_out(n_regions: int = 62) -> AtlasSourceOutput:
    """Helper to create synthetic AtlasSourceOutput with LH and RH SourceSpaces."""
    n_per_hemi = n_regions // 2
    n_verts = n_per_hemi * 4

    # Synthetic 3D coordinates on sphere
    phi = np.linspace(0, np.pi, n_verts)
    theta = np.linspace(0, 2 * np.pi, n_verts)
    rr_lh = np.column_stack([np.sin(phi) * np.cos(theta) - 20.0, np.sin(phi) * np.sin(theta), np.cos(phi)])
    rr_rh = np.column_stack([np.sin(phi) * np.cos(theta) + 20.0, np.sin(phi) * np.sin(theta), np.cos(phi)])

    tris_lh = np.array([[i, (i + 1) % n_verts, (i + 2) % n_verts] for i in range(0, n_verts - 2, 2)])
    tris_rh = np.array([[i, (i + 1) % n_verts, (i + 2) % n_verts] for i in range(0, n_verts - 2, 2)])

    s0 = {
        "vertno": np.arange(n_verts),
        "type": "surf",
        "hemi": "lh",
        "inuse": np.ones(n_verts, dtype=int),
        "nuse": n_verts,
        "np": n_verts,
        "rr": rr_lh,
        "nn": np.zeros((n_verts, 3)),
        "tris": tris_lh,
        "use_tris": tris_lh,
        "ntri": len(tris_lh)
    }
    s1 = {
        "vertno": np.arange(n_verts),
        "type": "surf",
        "hemi": "rh",
        "inuse": np.ones(n_verts, dtype=int),
        "nuse": n_verts,
        "np": n_verts,
        "rr": rr_rh,
        "nn": np.zeros((n_verts, 3)),
        "tris": tris_rh,
        "use_tris": tris_rh,
        "ntri": len(tris_rh)
    }
    src = mne.SourceSpaces([s0, s1])

    labels = []
    for i in range(n_per_hemi):
        lbl_lh = mne.Label(
            vertices=np.array([2 * i, 2 * i + 1], dtype=int),
            hemi="lh",
            name=f"CerebrA_Region_{i+1:02d}",
            subject="synthetic"
        )
        labels.append(lbl_lh)

    for i in range(n_per_hemi):
        lbl_rh = mne.Label(
            vertices=np.array([2 * i, 2 * i + 1], dtype=int),
            hemi="rh",
            name=f"CerebrA_Region_{i+1+n_per_hemi:02d}",
            subject="synthetic"
        )
        labels.append(lbl_rh)

    return AtlasSourceOutput(
        src=src,
        cerebra_labels=labels,
        total_sources=2 * n_verts
    )


class TestStep5StatsVisualization(unittest.TestCase):
    """Test suite for step5_stats_visualization."""

    def setUp(self):
        """Set up temporary directory and test data."""
        self.temp_dir = tempfile.mkdtemp()
        self.n_subjects = 10
        self.n_regions = 62
        self.n_sig = 5
        self.mra_df = _generate_synthetic_mra_df(
            n_subjects=self.n_subjects,
            n_regions=self.n_regions,
            n_significant=self.n_sig,
            random_state=42
        )
        self.config = StatsVizConfig(
            condition_a="rest",
            condition_b="video1",
            n_permutations=5000,
            p_threshold=0.05,
            output_dir=self.temp_dir,
            random_state=42,
            dpi=100
        )
        self.src_out = _create_synthetic_src_out(self.n_regions)

    def tearDown(self):
        """Clean up temporary directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_permutation_test_vectorized_p_values(self):
        """Test that significant regions are detected with low p-values."""
        out = run_stats_visualization(self.mra_df, self.config)

        self.assertIsInstance(out, StatsVisualizationOutput)
        self.assertEqual(len(out.stats_df), self.n_regions)

        # First n_sig regions should be detected as significant
        sig_head = out.stats_df.iloc[:self.n_sig]
        self.assertTrue(sig_head["significant"].all())
        self.assertTrue((sig_head["p_value"] < 0.05).all())

        # Mean diff for significant regions should be positive around ~4.0
        self.assertTrue((sig_head["mean_diff"] > 2.0).all())

    def test_stats_dataframe_schema(self):
        """Test the schema and column names of stats_df."""
        out = run_stats_visualization(self.mra_df, self.config)

        expected_columns = [
            "region_name",
            "mean_a",
            "mean_b",
            "mean_diff",
            "p_value",
            "significant"
        ]
        self.assertListEqual(list(out.stats_df.columns), expected_columns)
        self.assertFalse(out.stats_df.isna().any().any())

        # Check saved CSV file exists on disk
        csv_file = os.path.join(self.temp_dir, "permutation_test_results.csv")
        self.assertTrue(os.path.exists(csv_file))

    def test_figure_generation_and_paths(self):
        """Test that figure files are generated and properly referenced."""
        out = run_stats_visualization(self.mra_df, self.config)

        self.assertGreater(len(out.figure_paths), 0)
        for fig_path in out.figure_paths:
            self.assertTrue(os.path.exists(fig_path), f"Figure not found: {fig_path}")
            self.assertGreater(os.path.getsize(fig_path), 0)

    def test_missing_columns_raises_error(self):
        """Test that missing required columns raises ValueError."""
        bad_df = self.mra_df.drop(columns=["mean_activation_na_m"])
        with self.assertRaises(ValueError):
            run_stats_visualization(bad_df, self.config)

    def test_no_paired_subjects_raises_error(self):
        """Test error when no overlapping subjects exist between conditions."""
        unpaired_records = [
            {"subject_id": "sub-01", "condition": "rest", "region_name": "R1", "mean_activation_na_m": 1.0},
            {"subject_id": "sub-02", "condition": "video1", "region_name": "R1", "mean_activation_na_m": 2.0},
        ]
        unpaired_df = pd.DataFrame(unpaired_records)
        with self.assertRaises(ValueError):
            run_stats_visualization(unpaired_df, self.config)

    def test_reproducibility_with_seed(self):
        """Test that identical seeds produce identical p-values."""
        out1 = run_stats_visualization(self.mra_df, self.config)
        out2 = run_stats_visualization(self.mra_df, self.config)

        np.testing.assert_array_almost_equal(
            out1.stats_df["p_value"].to_numpy(),
            out2.stats_df["p_value"].to_numpy()
        )

    def test_plot_brain_8views_generation(self):
        """Test 8-view cortical brain maps generation per subject and condition."""
        small_df = self.mra_df[self.mra_df["subject_id"].isin(["sub-01", "sub-02"])].copy()
        brain_maps = plot_brain_8views(
            all_subjects_mra_df=small_df,
            src_out=self.src_out,
            output_dir=self.temp_dir,
            dpi=100
        )

        # 2 subjects x 2 conditions = 4 brain maps
        self.assertEqual(len(brain_maps), 4)
        for p in brain_maps:
            self.assertTrue(os.path.exists(p), f"Brain map figure missing: {p}")
            self.assertGreater(os.path.getsize(p), 0)
            self.assertTrue(p.endswith("_8views.png"))

    def test_run_stats_visualization_with_brain_maps_integration(self):
        """Test end-to-end Step 5 execution with src_out passed."""
        small_df = self.mra_df[self.mra_df["subject_id"].isin(["sub-01", "sub-02"])].copy()
        config = StatsVizConfig(
            condition_a="rest",
            condition_b="video1",
            n_permutations=1000,
            p_threshold=0.05,
            output_dir=self.temp_dir,
            random_state=42,
            src_out=self.src_out,
            dpi=100
        )
        out = run_stats_visualization(small_df, config)

        self.assertIsInstance(out, StatsVisualizationOutput)
        # 3 statistical plots + 4 brain maps = 7 total figure paths
        self.assertEqual(len(out.figure_paths), 7)
        for fig_path in out.figure_paths:
            self.assertTrue(os.path.exists(fig_path))

    def test_load_surface_mesh_fallback(self):
        """Test surface mesh loading with fallback to SourceSpace."""
        coords_lh, tris_lh, coords_rh, tris_rh = _load_surface_mesh(
            self.src_out, subjects_dir="/non/existent/path"
        )
        self.assertGreater(len(coords_lh), 0)
        self.assertGreater(len(coords_rh), 0)
        self.assertGreater(len(tris_lh), 0)
        self.assertGreater(len(tris_rh), 0)

    def test_map_labels_to_triangles(self):
        """Test mapping parcel MRA values to triangle face averages."""
        coords_lh, tris_lh, coords_rh, tris_rh = _load_surface_mesh(self.src_out)
        sub_df = self.mra_df[(self.mra_df["subject_id"] == "sub-01") & (self.mra_df["condition"] == "rest")]
        tri_vals_lh, tri_vals_rh = _map_labels_to_triangles(
            self.src_out.cerebra_labels, sub_df, coords_lh, tris_lh, coords_rh, tris_rh
        )
        self.assertEqual(len(tri_vals_lh), len(tris_lh))
        self.assertEqual(len(tri_vals_rh), len(tris_rh))
        self.assertTrue(np.all(np.isfinite(tri_vals_lh)))
        self.assertTrue(np.all(np.isfinite(tri_vals_rh)))


if __name__ == "__main__":
    unittest.main()

