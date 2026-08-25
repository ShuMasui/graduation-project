# 高密度EEG解析 再現実験 プログラム設計書 (Implementation Design)

本ドキュメントは、[02-processing-flow.md](file:///Users/shumasui/Documents/school/graduate-project/docs/exp-reproduce/02-processing-flow.md) および [03-impl-rule.md](file:///Users/shumasui/Documents/school/graduate-project/docs/exp-reproduce/03-impl-rule.md) に基づき、各ステップ（モジュール）間の **「データ受け渡し契約（Interface Contract）」**、**「関数の引数・戻り値型定義」**、および **「順方向単方向依存ルール（Forward-Only Dependency）」** を具体的に定めたプログラム設計書です。

---

## 1. モジュール間連携とデータ契約の基本方針

### 1.1 順方向単方向参照ルール (Forward-Only Dependency Rule)
- **モジュール間の直接結合・逆方向参照の禁止**:
  - 後段のモジュールを参照すること、および兄弟モジュールの内部ロジック（`main.py`, `types.py`）を参照することは固く禁止します。
- **許可される唯一の参照**:
  - **自モジュールより前段（上流）のステップが公開する `output.py`（出力データ型 DTO）のインポートのみ** を許可します。
  - 各モジュールは前段の `Output` クラスを関数引数の型注釈として受け取り、自身の `output.py` で定義した `Output` クラスを返します。

```text
【許可される参照関係】
Step N の main.py  --->  Step (N-1) の output.py (型参照のみ)
                      x   Step (N-1) の main.py / types.py (参照禁止)
                      x   Step (N+1) の 全ファイル (逆方向参照禁止)
```

### 1.2 データ型の不変性 (Immutability)
- モジュール間で受け渡されるデータはすべて `@dataclass(frozen=True)` で定義し、後段のモジュールによる破壊的変更（副作用）を防止します。
- 数値データは NumPy 配列・Pandas DataFrame・MNE 標準オブジェクトとし、物理単位（$\text{Hz}$, $\text{dB}$, $\text{nA/m}$）を型定義に明記します。

---

## 2. パイプライン全体のデータ受け渡し契約図

```mermaid
flowchart TD
    subgraph Phase 1: 事前準備（共通モデル構築）
        Cfg0A[GeometryBEMConfig] --> M0A["step0a_geometry_bem.main.run_geometry_bem()"]
        M0A --> Out0A["GeometryBEMOutput<br>(bem_model, surfaces)"]

        Out0A --> M0B["step0b_atlas_source.main.run_atlas_source()"]
        Cfg0B[AtlasSourceConfig] --> M0B
        M0B --> Out0B["AtlasSourceOutput<br>(src, cerebra_labels)"]

        Out0A --> M0C["step0c_forward_model.main.run_forward_model()"]
        Out0B --> M0C
        Cfg0C[ForwardModelConfig] --> M0C
        M0C --> Out0C["ForwardModelOutput<br>(fwd, trans, info)"]
    end

    subgraph Phase 2: データ解析（被験者・試行別）
        Cfg1[PreprocessingConfig] --> M1["step1_preprocessing.main.run_preprocessing()"]
        M1 --> Out1["PreprocessedEEGOutput<br>(cleaned_raw, 125Hz)"]

        Out1 --> M2["step2_noise_covariance.main.run_noise_covariance()"]
        Cfg2[NoiseCovConfig] --> M2
        M2 --> Out2["CovarianceLambdaOutput<br>(noise_cov, lambda2)"]

        Out0C -.-> M3["step3_source_localization.main.run_source_localization()"]
        Out1 --> M3
        Out2 --> M3
        Cfg3[SourceLocConfig] --> M3
        M3 --> Out3["SourceEstimateOutput<br>(stc: eLORETA)"]

        Out3 --> M4["step4_parcellation.main.run_parcellation()"]
        Out0B -.-> M4
        Cfg4[SubjectMetadata] --> M4
        M4 --> Out4["RegionalActivationOutput<br>(MRA DataFrame)"]

        Out4 --> M5["step5_stats_visualization.main.run_stats_visualization()"]
        Cfg5[StatsVizConfig] --> M5
        M5 --> Out5["StatsVisualizationOutput<br>(p-values, figures)"]
    end
```

---

## 3. 各ステップのモジュール契約仕様

---

### Step 0-A: テンプレート幾何再構築 & 3層BEM抽出 (`step0a_geometry_bem`)

#### 1. 内部型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class GeometryBEMConfig:
    template_nii_path: str       # MNI-ICBM152 テンプレート画像パス (.nii)
    subjects_dir: str            # FreeSurfer 出力先ディレクトリ
    subject_name: str = "icbm152"# 被験者識別名
    conductivity: tuple[float, float, float] = (0.33, 0.0042, 0.33)  # 脳・頭蓋骨・皮膚の伝導率 (S/m)
    ico_resolution: int = 4      # BEM サーフェスメッシュの解像度 (ico-4: 2562 vertices/surface)
```

#### 2. 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
import mne

@dataclass(frozen=True)
class GeometryBEMOutput:
    subjects_dir: str                       # FreeSurfer 出力ベースディレクトリ
    subject_name: str                       # 被験者名 ('icbm152')
    bem_surfaces_path: str                  # BEM サーフェスファイル (*-bem.fif)
    bem_solution: mne.bem.ConductorModel   # 3層 BEM 電気伝導モデルオブジェクト
```

#### 3. 関数シグネチャ (`main.py`)
```python
from .types import GeometryBEMConfig
from .output import GeometryBEMOutput

def run_geometry_bem(config: GeometryBEMConfig) -> GeometryBEMOutput:
    """標準脳MRIから3層BEM伝導解モデルを作成する。"""
    ...
```

---

### Step 0-B: CerebrA変換 & ソース空間作成 (`step0b_atlas_source`)

#### 1. 内部型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class AtlasSourceConfig:
    cerebra_nii_path: str        # CerebrA アトラスラベル画像パス (.nii)
    cerebra_csv_path: str        # CerebrA ラベル名対応CSVパス
    spacing: str = "oct6"        # ソース空間グリッド密度 (oct-6: 約31,554点)
    surface: str = "white"       # 配置対象サーフェス ('white' or 'pial')
```

#### 2. 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
from typing import List
import mne

@dataclass(frozen=True)
class AtlasSourceOutput:
    src: mne.SourceSpaces                  # 定義されたソース空間 (約31,554点)
    cerebra_labels: List[mne.Label]       # CerebrA 62皮質領域の Label オブジェクトリスト
    total_sources: int                     # 総ソース点数 (int: 31,554)
```

#### 3. 関数シグネチャ (`main.py`)
```python
from modules.step0a_geometry_bem.output import GeometryBEMOutput  # 前段出力のみインポート
from .types import AtlasSourceConfig
from .output import AtlasSourceOutput

def run_atlas_source(bem_out: GeometryBEMOutput, config: AtlasSourceConfig) -> AtlasSourceOutput:
    """CerebrAアトラスをFreeSurfer空間へマップし、皮質ソース空間と62領域ラベルを生成する。"""
    ...
```

---

### Step 0-C: 電極共登録 & 順モデル一括計算 (`step0c_forward_model`)

#### 1. 内部型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ForwardModelConfig:
    montage_name: str = "GSN-HydroCel-128" # 電極配置名 ('GSN-HydroCel-128' or 'standard_64')
    eeg_channels_count: int = 128          # 電極数
    mindist: float = 5.0                   # 内頭蓋骨面からの最小距離 (mm)
```

#### 2. 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
import mne

@dataclass(frozen=True)
class ForwardModelOutput:
    forward: mne.Forward                   # 順モデル / Lead Field 行列 (128ch x 31554 sources)
    trans: mne.transforms.Transform        # 電極-頭部座標変換マトリックス
    info: mne.Info                         # 電極位置メタ情報
```

#### 3. 関数シグネチャ (`main.py`)
```python
from modules.step0a_geometry_bem.output import GeometryBEMOutput
from modules.step0b_atlas_source.output import AtlasSourceOutput
from .types import ForwardModelConfig
from .output import ForwardModelOutput

def run_forward_model(
    bem_out: GeometryBEMOutput,
    src_out: AtlasSourceOutput,
    config: ForwardModelConfig
) -> ForwardModelOutput:
    """電極モンタージュを共登録し、全被験者共通の順モデル(Lead Field)を事前計算する。"""
    ...
```

---

### Step 1: 生EEGデータ前処理 (`step1_preprocessing`)

#### 1. 内部型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class PreprocessingConfig:
    raw_eeg_path: str            # 生EEGデータファイルパス
    target_sampling_rate: float = 125.0  # リサンプリング周波数 (Hz)
    l_freq: float = 1.0          # ハイパス遮断周波数 (Hz)
    h_freq: float = 50.0         # ローパス遮断周波数 (Hz)
    apply_prep: bool = True      # PREP異常チャンネル補間・再参照の適用
    ica_n_components: int = 20   # FastICA 分解成分数
```

#### 2. 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
from typing import List
import mne

@dataclass(frozen=True)
class PreprocessedEEGOutput:
    raw: mne.io.BaseRaw                    # アーティファクト除去済みのクリーンRawデータ
    sampling_rate: float                   # サンプリングレート (125.0 Hz)
    bad_channels: List[str]                # 補間された不良電極名リスト
    removed_ica_components: List[int]      # 除去されたノイズICA成分インデックス
```

#### 3. 関数シグネチャ (`main.py`)
```python
from .types import PreprocessingConfig
from .output import PreprocessedEEGOutput

def run_preprocessing(config: PreprocessingConfig) -> PreprocessedEEGOutput:
    """生EEGデータに対してダウンサンプリング、フィルタ、PREP補間、ICA除去を実行する。"""
    ...
```

---

### Step 2: ノイズ共分散 & 動的SNR・正則化パラメータ算出 (`step2_noise_covariance`)

#### 1. 内部型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class NoiseCovConfig:
    tmin: float = 0.0            # 共分散推定開始時刻 (秒)
    tmax: float | None = None    # 共分散推定終了時刻 (None = 全区間)
```

#### 2. 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
import mne

@dataclass(frozen=True)
class CovarianceLambdaOutput:
    noise_cov: mne.Covariance              # ノイズ共分散行列 C
    snr_db: float                          # 信号対雑音比 SNR = 10 * log10(P / sigma^2) (dB)
    lambda2: float                         # 動的正則化パラメータ lambda^2 = 1.0 / (SNR^2)
```

#### 3. 関数シグネチャ (`main.py`)
```python
from modules.step1_preprocessing.output import PreprocessedEEGOutput
from .types import NoiseCovConfig
from .output import CovarianceLambdaOutput

def run_noise_covariance(
    eeg_out: PreprocessedEEGOutput,
    config: NoiseCovConfig
) -> CovarianceLambdaOutput:
    """ノイズ共分散を推定し、信号SNRから動的正則化パラメータ lambda^2 を算出する。"""
    ...
```

---

### Step 3: eLORETA 音源推定 (`step3_source_localization`)

#### 1. 内部型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SourceLocConfig:
    method: str = "eLORETA"      # 逆問題ソルバー ('eLORETA')
    loose: float = 0.2           # 双極子の法線拘束パラメータ (0.2: loose orientation)
    depth: float = 0.8           # 深度重み付けパラメータ
```

#### 2. 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
import mne

@dataclass(frozen=True)
class SourceEstimateOutput:
    stc: mne.SourceEstimate                # 推定されたソース空間電流密度 (nA/m, 31554点 x 時間)
    method: str                            # 'eLORETA'
    lambda2_used: float                    # 適用された lambda^2 値
```

#### 3. 関数シグネチャ (`main.py`)
```python
from modules.step0c_forward_model.output import ForwardModelOutput
from modules.step1_preprocessing.output import PreprocessedEEGOutput
from modules.step2_noise_covariance.output import CovarianceLambdaOutput
from .types import SourceLocConfig
from .output import SourceEstimateOutput

def run_source_localization(
    fwd_out: ForwardModelOutput,
    eeg_out: PreprocessedEEGOutput,
    cov_out: CovarianceLambdaOutput,
    config: SourceLocConfig
) -> SourceEstimateOutput:
    """逆作用素を作成し、eLORETAによりソース空間電流密度を推定する。"""
    ...
```

---

### Step 4: CerebrA 領域集約 (MRA算出) (`step4_parcellation`)

#### 1. 内部型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SubjectMetadata:
    subject_id: str              # 被験者ID (例: 'sub-01')
    condition: str               # 実験条件 (例: 'rest', 'video1', 'video2')
    duration_sec: float = 90.0   # 解析時間区間 (秒)
```

#### 2. 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
from typing import List
import pandas as pd

@dataclass(frozen=True)
class RegionalActivationOutput:
    # mra_df 列: ['subject_id', 'condition', 'region_name', 'mean_activation_na_m']
    mra_df: pd.DataFrame                   # 62領域ごとの平均活動量テーブル (DataFrame)
    region_names: List[str]                # 62個の領域名リスト
```

#### 3. 関数シグネチャ (`main.py`)
```python
from modules.step0b_atlas_source.output import AtlasSourceOutput
from modules.step3_source_localization.output import SourceEstimateOutput
from .types import SubjectMetadata
from .output import RegionalActivationOutput

def run_parcellation(
    stc_out: SourceEstimateOutput,
    src_out: AtlasSourceOutput,
    metadata: SubjectMetadata
) -> RegionalActivationOutput:
    """全ソース点の推定値をCerebrAの62皮質領域ごとに空間・時間平均(MRA)して集約する。"""
    ...
```

---

### Step 5: 統計検定 & 3D脳活動可視化 (`step5_stats_visualization`)

#### 1. 内部型 (`types.py`)
```python
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class StatsVizConfig:
    condition_a: str             # 比較条件A (例: 'rest')
    condition_b: str             # 比較条件B (例: 'video1')
    n_permutations: int = 10000  # 置換検定の反復回数
    p_threshold: float = 0.05    # 有意水準
    output_dir: str = "./results"# 図・テーブル出力先ディレクトリ
```

#### 2. 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
from typing import List
import pandas as pd

@dataclass(frozen=True)
class StatsVisualizationOutput:
    # stats_df 列: ['region_name', 'mean_diff', 'p_value', 'significant']
    stats_df: pd.DataFrame                 # 62領域の置換検定結果テーブル
    figure_paths: List[str]                # 出力された3D/2D可視化画像ファイルパス一覧
```

#### 3. 関数シグネチャ (`main.py`)
```python
import pandas as pd
from .types import StatsVizConfig
from .output import StatsVisualizationOutput

def run_stats_visualization(
    all_subjects_mra_df: pd.DataFrame,
    config: StatsVizConfig
) -> StatsVisualizationOutput:
    """全被験者の領域別活動量に対して対応のある置換検定を行い、3D脳マップを作図・保存する。"""
    ...
```

---

## 4. 全体オーケストレーション実行例 (`exp-reproduce/main.py`)

最上位モジュールは、各ステップの `Output` をバケツリレーのように渡すだけの非常に薄く見通しの良い構造になります。

```python
"""
exp-reproduce/main.py
高密度EEG解析パイプライン 全体オーケストレーション
"""
import os
import pandas as pd

# Phase 1 モジュール
from modules.step0a_geometry_bem.main import run_geometry_bem
from modules.step0a_geometry_bem.types import GeometryBEMConfig
from modules.step0b_atlas_source.main import run_atlas_source
from modules.step0b_atlas_source.types import AtlasSourceConfig
from modules.step0c_forward_model.main import run_forward_model
from modules.step0c_forward_model.types import ForwardModelConfig

# Phase 2 モジュール
from modules.step1_preprocessing.main import run_preprocessing
from modules.step1_preprocessing.types import PreprocessingConfig
from modules.step2_noise_covariance.main import run_noise_covariance
from modules.step2_noise_covariance.types import NoiseCovConfig
from modules.step3_source_localization.main import run_source_localization
from modules.step3_source_localization.types import SourceLocConfig
from modules.step4_parcellation.main import run_parcellation
from modules.step4_parcellation.types import SubjectMetadata
from modules.step5_stats_visualization.main import run_stats_visualization
from modules.step5_stats_visualization.types import StatsVizConfig


def main():
    print("=== [Phase 1] 共通モデル構築開始 ===")
    bem_cfg = GeometryBEMConfig(
        template_nii_path="docs/exp-reproduce/mni_icbm152_nlin_sym_09c_CerebrA_minc2/mni_icbm152_t1_tal_nlin_sym_09c.nii",
        subjects_dir="./subjects"
    )
    bem_out = run_geometry_bem(bem_cfg)

    atlas_cfg = AtlasSourceConfig(
        cerebra_nii_path="docs/exp-reproduce/mni_icbm152_nlin_sym_09c_CerebrA_minc2/CerebrA.nii",
        cerebra_csv_path="docs/exp-reproduce/mni_icbm152_nlin_sym_09c_CerebrA_minc2/CerebrA_LabelDetails.csv"
    )
    src_out = run_atlas_source(bem_out, atlas_cfg)

    fwd_cfg = ForwardModelConfig(montage_name="GSN-HydroCel-128")
    fwd_out = run_forward_model(bem_out, src_out, fwd_cfg)

    print("=== [Phase 2] データ解析開始 ===")
    subjects = ["sub-01", "sub-02"]
    conditions = ["rest", "video1"]
    all_mra_records = []

    for sub in subjects:
        for cond in conditions:
            # 1. 前処理
            prep_cfg = PreprocessingConfig(raw_eeg_path=f"./data/{sub}_{cond}_raw.fif")
            eeg_out = run_preprocessing(prep_cfg)

            # 2. ノイズ共分散・正則化
            cov_cfg = NoiseCovConfig()
            cov_out = run_noise_covariance(eeg_out, cov_cfg)

            # 3. 音源推定
            loc_cfg = SourceLocConfig(method="eLORETA")
            stc_out = run_source_localization(fwd_out, eeg_out, cov_out, loc_cfg)

            # 4. 領域集約
            meta = SubjectMetadata(subject_id=sub, condition=cond)
            parc_out = run_parcellation(stc_out, src_out, meta)
            all_mra_records.append(parc_out.mra_df)

    # 5. 全体統計検定 & 可視化
    all_mra_df = pd.concat(all_mra_records, ignore_index=True)
    viz_cfg = StatsVizConfig(condition_a="rest", condition_b="video1", output_dir="./results")
    stats_out = run_stats_visualization(all_mra_df, viz_cfg)

    print("=== パイプライン実行完了 ===")
    print(f"結果テーブル:\n{stats_out.stats_df.head()}")


if __name__ == "__main__":
    main()
```
