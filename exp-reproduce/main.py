"""
exp-reproduce/main.py
High-Density EEG Analysis Reproducibility Pipeline Orchestrator.

Linear workflow executing:
- Phase 1 (Common Models): Step 0-A (BEM) -> Step 0-B (Atlas/Source) -> Step 0-C (Forward Model)
- Phase 2 (Trial Processing): Step 1 (Preprocessing) -> Step 2 (Noise Cov/SNR) -> Step 3 (eLORETA) -> Step 4 (MRA)
- Phase 3 (Group Stats & Viz): Step 5 (Paired Permutation Test & Publication Figures)
"""
import os
import sys
import time
import logging
from typing import List, Optional, Tuple
import pandas as pd

# --- Phase 1: Common Model Modules ---
from modules.step0a_geometry_bem.main import run_geometry_bem
from modules.step0a_geometry_bem.types import GeometryBEMConfig
from modules.step0a_geometry_bem.output import GeometryBEMOutput
from modules.step0b_atlas_source.main import run_atlas_source
from modules.step0b_atlas_source.types import AtlasSourceConfig
from modules.step0b_atlas_source.output import AtlasSourceOutput
from modules.step0c_forward_model.main import run_forward_model
from modules.step0c_forward_model.types import ForwardModelConfig
from modules.step0c_forward_model.output import ForwardModelOutput

# --- Phase 2: Data Analysis Modules ---
from modules.step1_preprocessing.main import run_preprocessing
from modules.step1_preprocessing.types import PreprocessingConfig
from modules.step2_noise_covariance.main import run_noise_covariance
from modules.step2_noise_covariance.types import NoiseCovConfig
from modules.step3_source_localization.main import run_source_localization
from modules.step3_source_localization.types import SourceLocConfig
from modules.step4_parcellation.main import run_parcellation
from modules.step4_parcellation.types import SubjectMetadata

# --- Phase 3: Statistical Testing & Visualization ---
from modules.step5_stats_visualization.main import run_stats_visualization
from modules.step5_stats_visualization.types import StatsVizConfig
from modules.step5_stats_visualization.output import StatsVisualizationOutput

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Orchestrator")


def prepare_common_models(
    template_nii_path: str,
    cerebra_nii_path: str,
    cerebra_csv_path: str,
    subjects_dir: str,
    montage_name: str = "GSN-HydroCel-128",
    force_recompute: bool = False
) -> Tuple[GeometryBEMOutput, AtlasSourceOutput, ForwardModelOutput]:
    """Prepare common geometry, source spaces, and forward solution (Phase 1).

    Parameters:
        template_nii_path: Path to MNI-ICBM152 template MRI.
        cerebra_nii_path: Path to CerebrA atlas NIfTI/MINC file.
        cerebra_csv_path: Path to CerebrA labels metadata CSV.
        subjects_dir: FreeSurfer subjects directory.
        montage_name: Standard EEG montage name (default: 'GSN-HydroCel-128').
        force_recompute: Recompute even if cached files exist.

    Returns:
        Tuple containing GeometryBEMOutput, AtlasSourceOutput, and ForwardModelOutput.
    """
    logger.info("=== [Phase 1] 共通モデルの準備開始 ===")

    # 1. Step 0-A: 3-layer BEM Conductor Model
    logger.info("Step 0-A: BEMモデルの構築...")
    bem_cfg = GeometryBEMConfig(
        template_nii_path=template_nii_path,
        subjects_dir=subjects_dir,
        overwrite=force_recompute
    )
    bem_out = run_geometry_bem(bem_cfg)

    # 2. Step 0-B: Source Space & CerebrA Labels
    logger.info("Step 0-B: ソース空間およびCerebrA領域定義の生成...")
    atlas_cfg = AtlasSourceConfig(
        cerebra_nii_path=cerebra_nii_path,
        cerebra_csv_path=cerebra_csv_path,
        overwrite=force_recompute
    )
    src_out = run_atlas_source(bem_out, atlas_cfg)

    # 3. Step 0-C: Forward Model (Lead Field)
    logger.info("Step 0-C: 電極共登録 & 順モデルの計算...")
    fwd_cfg = ForwardModelConfig(
        montage_name=montage_name,
        overwrite=force_recompute
    )
    fwd_out = run_forward_model(bem_out, src_out, fwd_cfg)

    logger.info(
        "=== [Phase 1] 共通モデルの準備完了: ソース点数=%d, 電極数=%d ===",
        src_out.total_sources,
        fwd_out.forward["nchan"] if hasattr(fwd_out.forward, "__getitem__") else -1
    )
    return bem_out, src_out, fwd_out


def run_pipeline(
    data_dir: str,
    subject_ids: List[str],
    conditions: List[str],
    output_dir: str = "./results",
    template_nii_path: str = "atlas/mni_icbm152_CerebrA_tal_nlin_sym_09c.nii",
    cerebra_nii_path: str = "atlas/mni_icbm152_CerebrA_tal_nlin_sym_09c.nii",
    cerebra_csv_path: str = "atlas/CerebrA_LabelDetails.csv",
    subjects_dir: str = "./subjects",
    montage_name: str = "GSN-HydroCel-128",
    force_recompute_common: bool = False,
    n_permutations: int = 10000,
    p_threshold: float = 0.05,
    random_state: int = 42
) -> Optional[StatsVisualizationOutput]:
    """Execute complete end-to-end EEG analysis pipeline.

    Parameters:
        data_dir: Path to directory containing subject EEG fif files.
        subject_ids: List of subject identifiers (e.g. ['sub-01', 'sub-02']).
        conditions: List of experimental conditions (e.g. ['rest', 'video1']).
        output_dir: Destination directory for summary tables and plots.
        template_nii_path: Path to template MRI NIfTI.
        cerebra_nii_path: Path to CerebrA atlas file.
        cerebra_csv_path: Path to CerebrA labels CSV.
        subjects_dir: FreeSurfer directory.
        montage_name: Standard electrode montage name.
        force_recompute_common: Force recomputation of Phase 1 models.
        n_permutations: Number of permutation test iterations.
        p_threshold: Significance threshold alpha.
        random_state: Random seed for permutation test.

    Returns:
        StatsVisualizationOutput if pipeline completes successfully, else None.
    """
    pipeline_start_time = time.time()
    logger.info("==================================================")
    logger.info(" 高密度EEG解析 再現実験 パイプライン開始")
    logger.info("==================================================")
    os.makedirs(output_dir, exist_ok=True)

    # パス自動解決 (カレントディレクトリが repo root または exp-reproduce いずれにも対応)
    def _resolve(p: str) -> str:
        if os.path.exists(p):
            return p
        alt = os.path.join("exp-reproduce", p)
        if os.path.exists(alt):
            return alt
        if p.startswith("exp-reproduce/"):
            alt2 = p.replace("exp-reproduce/", "", 1)
            if os.path.exists(alt2):
                return alt2
        return p

    resolved_template = _resolve(template_nii_path)
    resolved_cerebra_nii = _resolve(cerebra_nii_path)
    resolved_cerebra_csv = _resolve(cerebra_csv_path)
    resolved_subjects_dir = _resolve(subjects_dir)

    # ------------------------------------------------------------------
    # Phase 1: 共通モデルの準備 (Common Head Model & Lead Field)
    # ------------------------------------------------------------------
    bem_out, src_out, fwd_out = prepare_common_models(
        template_nii_path=resolved_template,
        cerebra_nii_path=resolved_cerebra_nii,
        cerebra_csv_path=resolved_cerebra_csv,
        subjects_dir=resolved_subjects_dir,
        montage_name=montage_name,
        force_recompute=force_recompute_common
    )

    # ------------------------------------------------------------------
    # Phase 2: 各被験者・条件の解析 (Trial Processing Loop)
    # ------------------------------------------------------------------
    logger.info("=== [Phase 2] 被験者データ解析開始 (被験者数: %d) ===", len(subject_ids))
    all_mra_records: List[pd.DataFrame] = []

    for sub in subject_ids:
        for cond in conditions:
            # Candidate file paths
            raw_fif_path = os.path.join(data_dir, f"{sub}_{cond}_raw.fif")
            if not os.path.exists(raw_fif_path):
                # Try fallback filename without _raw suffix
                alt_path = os.path.join(data_dir, f"{sub}_{cond}.fif")
                if os.path.exists(alt_path):
                    raw_fif_path = alt_path
                else:
                    logger.warning("データが見つからないためスキップします: %s", raw_fif_path)
                    continue

            logger.info("--- 解析開始: 被験者=%s, 条件=%s ---", sub, cond)
            try:
                # Step 1: 生EEGデータ前処理 (リサンプル、フィルタ、PREP、ICA)
                prep_cfg = PreprocessingConfig(raw_eeg_path=raw_fif_path)
                eeg_out = run_preprocessing(prep_cfg)

                # Step 2: ノイズ共分散推定 & 動的SNR / 正則化パラメータ算出
                cov_cfg = NoiseCovConfig()
                cov_out = run_noise_covariance(eeg_out, cov_cfg)
                logger.info(
                    "  [Step 2] 推定SNR: %.2f dB, lambda2: %.6f",
                    cov_out.snr_db,
                    cov_out.lambda2
                )

                # Step 3: eLORETA 音源推定
                loc_cfg = SourceLocConfig(method="eLORETA")
                stc_out = run_source_localization(fwd_out, eeg_out, cov_out, loc_cfg)

                # Step 4: CerebrA 62領域 平均活動量 (MRA) 集約
                meta = SubjectMetadata(subject_id=sub, condition=cond)
                parc_out = run_parcellation(stc_out, src_out, meta)

                all_mra_records.append(parc_out.mra_df)
                logger.info("  [Step 4] 領域集約完了: %d 領域", len(parc_out.mra_df))

            except Exception as e:
                logger.error(
                    "被験者 %s, 条件 %s の解析中にエラーが発生しました: %s",
                    sub,
                    cond,
                    str(e),
                    exc_info=True
                )

    if not all_mra_records:
        logger.error("処理可能な有効データが存在しませんでした。パイプラインを終了します。")
        return None

    # 全被験者・全条件の整然 DataFrame を結合して保存
    all_subjects_mra_df = pd.concat(all_mra_records, ignore_index=True)
    mra_csv_path = os.path.join(output_dir, "all_subjects_mra.csv")
    all_subjects_mra_df.to_csv(mra_csv_path, index=False)
    logger.info("全被験者の領域活動量データ (MRA) を保存しました: %s", mra_csv_path)

    # ------------------------------------------------------------------
    # Phase 3: 統計検定 (対応のある置換検定) & 可視化
    # ------------------------------------------------------------------
    if len(conditions) < 2:
        logger.warning("統計検定には2つ以上の条件が必要です。Phase 3 をスキップします。")
        return None

    logger.info("=== [Phase 3] 統計検定 & 可視化開始 (%s vs %s) ===", conditions[0], conditions[1])
    viz_cfg = StatsVizConfig(
        condition_a=conditions[0],
        condition_b=conditions[1],
        n_permutations=n_permutations,
        p_threshold=p_threshold,
        output_dir=output_dir,
        random_state=random_state
    )
    stats_out = run_stats_visualization(all_subjects_mra_df, viz_cfg)

    elapsed_time = time.time() - pipeline_start_time
    logger.info("==================================================")
    logger.info(" パイプライン全工程が正常に完了しました (所要時間: %.1f 秒)", elapsed_time)
    logger.info(" 統計結果CSV: %s", os.path.join(output_dir, "permutation_test_results.csv"))
    logger.info(" 生成図面数: %d 枚", len(stats_out.figure_paths))
    logger.info("==================================================")

    return stats_out


if __name__ == "__main__":
    # Sample run entrypoint
    run_pipeline(
        data_dir="./data",
        subject_ids=["sub-01", "sub-02"],
        conditions=["rest", "video1"],
        output_dir="./results"
    )
