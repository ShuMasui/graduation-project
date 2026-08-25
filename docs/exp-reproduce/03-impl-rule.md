# 高密度EEG解析 再現実験 実装規約書 (Implementation Rules)

本ドキュメントは、[02-processing-flow.md](file:///Users/shumasui/Documents/school/graduate-project/docs/exp-reproduce/02-processing-flow.md) で定義された処理フローに基づき、`exp-reproduce/` におけるプログラムのディレクトリ構造、モジュール設計規約、型定義ルール、および単体テスト方針を定めた実装規約書です。

---

## 1. モジュール設計の基本原則

本プロジェクトでは、コードの独立性と検証性を最大限に高めるため、以下の原則に従って実装を行います。

1. **ステップ単位の完全独立モジュール化**
   - 各フローステップ（Step 0-A 〜 Step 5）は完全に独立したサブディレクトリ（モジュール）として実装します。
   - モジュール間は直接依存せず、標準化された「出力データ型（Output DTO）」のみを通じて疎結合に連携します。
2. **ディレクトリ内の責務分離（4ファイル構成）**
   - **`main.py`**: 当該ステップのコア処理ロジックのみを記述。前段の `Output`（または設定）を入力として受け取り、自身の `Output` を返すエントリー関数を実装。
   - **`output.py`**: 当該モジュールが「次のフローへデータを渡す際のデータ型」のみを記述（`@dataclass` を推奨）。
   - **`types.py`**: モジュール内部で完結して使用する型定義、設定パラメータクラス、内部データ構造を記述。
   - **`test_main.py`**: Python 標準の `unittest` を用いた単体テストコード。
3. **上位層でのオーケストレーション**
   - ルート直下の `main.py` が各モジュールをインポートし、データの受け渡しと一連の実行フローを統括（オーケストレーション）します。
4. **PEP 8 準拠の命名規則**
   - ディレクトリ名・モジュール名・関数名・変数名: `snake_case`（小文字＋アンダースコア）
   - クラス名・データ型名: `PascalCase`（キャメルケース）
   - 定数名: `UPPER_SNAKE_CASE`
5. **単体テスト優先主義（Unit Test First）**
   - Python 標準の `unittest` を使用し、各モジュールが単体として正しく動作し、期待されるデータ型を出力するかのみを検証します。
   - 結合時のエラーや実データとの微調整は、研究者本人と対話しながら順次解消していきます。
6. **数学的説明性の重視とライブラリ機能の活用（ベクトル化演算の徹底）**
   - **数学的な説明性を重視したコード** にすることを徹底します。
   - 自前で `for` 文を回す処理を避け、NumPy や Pandas といった研究分野において実績と信頼性のあるライブラリの機能（行列演算・ブロードキャスト・ベクトル化処理）に頼ることで、数式とコードの一致度・再現性・処理速度を高めます。

---

## 2. ディレクトリ構造

```text
exp-reproduce/
├── .python-version                     # pyenv 環境定義 (exp-reproduce: Python 3.10)
├── main.py                             # 全体オーケストレーション（パイプライン結合実行スクリプト）
├── requirements.txt                    # 必要パッケージ一覧
│
└── modules/                            # 各処理ステップの独立モジュール群
    ├── step0a_geometry_bem/            # 【Step 0-A】テンプレート幾何再構築 & 3層BEM抽出
    │   ├── __init__.py
    │   ├── main.py                     # BEMサーフェス抽出・伝導モデル生成ロジック
    │   ├── types.py                    # 内部設定・幾何パラメータ型
    │   ├── output.py                   # BEMModelOutput (BEMモデル・サーフェスパス型)
    │   └── test_main.py                # 単体テスト (unittest)
    │
    ├── step0b_atlas_source/            # 【Step 0-B】CerebrA変換 & ソース空間作成
    │   ├── __init__.py
    │   ├── main.py                     # CerebrAラベル変換・約3万点ソース空間生成
    │   ├── types.py                    # アトラス設定・座標系型
    │   ├── output.py                   # AtlasSourceOutput (src, cerebra_labels型)
    │   └── test_main.py                # 単体テスト (unittest)
    │
    ├── step0c_forward_model/           # 【Step 0-C】電極共登録 & 順モデル計算
    │   ├── __init__.py
    │   ├── main.py                     # 電極位置アライメント・Lead Field一括計算
    │   ├── types.py                    # モンタージュ定義・変換パラメータ型
    │   ├── output.py                   # ForwardModelOutput (fwd型)
    │   └── test_main.py                # 単体テスト (unittest)
    │
    ├── step1_preprocessing/            # 【Step 1】生EEGデータ前処理
    │   ├── __init__.py
    │   ├── main.py                     # リサンプル・フィルタ・PREP・ICA除去
    │   ├── types.py                    # 前処理設定・フィルタパラメータ型
    │   ├── output.py                   # PreprocessedEEGOutput (クリーンRawデータ型)
    │   └── test_main.py                # 単体テスト (unittest)
    │
    ├── step2_noise_covariance/         # 【Step 2】ノイズ共分散 & 動的SNR計算
    │   ├── __init__.py
    │   ├── main.py                     # 共分散推定・SNR算出・lambda2決定ロジック
    │   ├── types.py                    # SNR計算設定型
    │   ├── output.py                   # CovarianceLambdaOutput (noise_cov, lambda2型)
    │   └── test_main.py                # 単体テスト (unittest)
    │
    ├── step3_source_localization/      # 【Step 3】eLORETA 音源推定
    │   ├── __init__.py
    │   ├── main.py                     # 逆作用素生成・eLORETA逆問題求解
    │   ├── types.py                    # 逆問題パラメータ型
    │   ├── output.py                   # SourceEstimateOutput (stc型)
    │   └── test_main.py                # 単体テスト (unittest)
    │
    ├── step4_parcellation/             # 【Step 4】CerebrA 62領域集約 (MRA)
    │   ├── __init__.py
    │   ├── main.py                     # ラベルごとの空間・時間平均活動量算出
    │   ├── types.py                    # 集約条件・領域リスト型
    │   ├── output.py                   # RegionalActivationOutput (MRA DataFrame型)
    │   └── test_main.py                # 単体テスト (unittest)
    │
    └── step5_stats_visualization/      # 【Step 5】統計検定 & 3D脳活動可視化
        ├── __init__.py
        ├── main.py                     # Paired Permutation Test & 3Dプロット生成
        ├── types.py                    # 検定設定・カラーマップ型
        ├── output.py                   # StatsVisualizationOutput (p値テーブル・画像パス型)
        └── test_main.py                # 単体テスト (unittest)
```

---

## 3. 各モジュールの実装仕様と入出力型定義

### Step 0-A: `step0a_geometry_bem`

- **役割**: 標準脳 MRI から 3層 BEM（皮膚・外頭蓋・内頭蓋）境界面を抽出・構築
- **`output.py` (出力型)**:

  ```python
  from dataclasses import dataclass
  import mne

  @dataclass(frozen=True)
  class GeometryBEMOutput:
      subjects_dir: str
      subject_name: str
      bem_model: mne.bem.ConductorModel
      bem_surfaces_dir: str
  ```

- **`main.py` (エントリー関数)**:
  ```python
  def run_geometry_bem(template_nii_path: str, subjects_dir: str) -> GeometryBEMOutput:
      ...
  ```
- **単体テスト観点 (`test_main.py`)**:
  - BEM モデルオブジェクトが正しく生成され、3層構造（conductivities=[0.33, 0.0042, 0.33]）が保持されているか。

---

### Step 0-B: `step0b_atlas_source`

- **役割**: CerebrA アトラスの変換と皮質上約 31,554 点のソース空間の生成
- **`output.py` (出力型)**:

  ```python
  from dataclasses import dataclass
  from typing import List
  import mne

  @dataclass(frozen=True)
  class AtlasSourceOutput:
      src: mne.SourceSpaces
      cerebra_labels: List[mne.Label]
      total_sources: int
  ```

- **`main.py` (エントリー関数)**:
  ```python
  def run_atlas_source(bem_out: GeometryBEMOutput, cerebr_nii_path: str) -> AtlasSourceOutput:
      ...
  ```
- **単体テスト観点 (`test_main.py`)**:
  - ソース空間 `src` の点数が期待値（約3万点）で生成され、62領域の `cerebra_labels` が欠落なく抽出できるか。

---

### Step 0-C: `step0c_forward_model`

- **役割**: 電極モンタージュの共登録および共通順モデル（Lead Field）の一括計算
- **`output.py` (出力型)**:

  ```python
  from dataclasses import dataclass
  import mne

  @dataclass(frozen=True)
  class ForwardModelOutput:
      forward: mne.Forward
      trans: mne.transforms.Transform
      info: mne.Info
  ```

- **`main.py` (エントリー関数)**:
  ```python
  def run_forward_model(bem_out: GeometryBEMOutput, src_out: AtlasSourceOutput, montage_name: str) -> ForwardModelOutput:
      ...
  ```
- **単体テスト観点 (`test_main.py`)**:
  - 順モデル `forward` のリードフィールド行列が正しい次元（電極数 $\times$ ソース点数）で生成されるか。

---

### Step 1: `step1_preprocessing`

- **役割**: 生 EEG のダウンサンプリング、フィルタ、PREP 異常電極補間、ICA アーティファクト除去
- **`output.py` (出力型)**:

  ```python
  from dataclasses import dataclass
  import mne

  @dataclass(frozen=True)
  class PreprocessedEEGOutput:
      raw: mne.io.BaseRaw
      sampling_rate: float
      bad_channels: list[str]
      removed_ica_components: list[int]
  ```

- **`main.py` (エントリー関数)**:
  ```python
  def run_preprocessing(raw_eeg_path: str) -> PreprocessedEEGOutput:
      ...
  ```
- **単体テスト観点 (`test_main.py`)**:
  - モックデータに対してリサンプル（125Hz）とフィルタ（1-50Hz）が適用され、クリーンな `Raw` オブジェクトが返るか。

---

### Step 2: `step2_noise_covariance`

- **役割**: ノイズ共分散行列の計算および動的 SNR / 正則化パラメータ（$\lambda^2 = 1/\text{SNR}^2$）の算出
- **`output.py` (出力型)**:

  ```python
  from dataclasses import dataclass
  import mne

  @dataclass(frozen=True)
  class CovarianceLambdaOutput:
      noise_cov: mne.Covariance
      snr_db: float
      lambda2: float
  ```

- **`main.py` (エントリー関数)**:
  ```python
  def run_noise_covariance(eeg_out: PreprocessedEEGOutput) -> CovarianceLambdaOutput:
      ...
  ```
- **単体テスト観点 (`test_main.py`)**:
  - 信号パワーから正しく SNR が計算され、$\lambda^2 = 1/\text{SNR}^2$ が正の有限値として算出されるか。

---

### Step 3: `step3_source_localization`

- **役割**: 順モデルとノイズ共分散から逆作用素を作成し、eLORETA による音源推定を実行
- **`output.py` (出力型)**:

  ```python
  from dataclasses import dataclass
  import mne

  @dataclass(frozen=True)
  class SourceEstimateOutput:
      stc: mne.SourceEstimate
      method: str  # 'eLORETA'
      lambda2: float
  ```

- **`main.py` (エントリー関数)**:
  ```python
  def run_source_localization(
      fwd_out: ForwardModelOutput,
      eeg_out: PreprocessedEEGOutput,
      cov_out: CovarianceLambdaOutput
  ) -> SourceEstimateOutput:
      ...
  ```
- **単体テスト観点 (`test_main.py`)**:
  - `apply_inverse_raw` に `method='eLORETA'` と `lambda2` が渡され、正しい時間長・ソース点数の `stc` が生成されるか。

---

### Step 4: `step4_parcellation`

- **役割**: 推定された全ソース点の活動を CerebrA の 62 皮質領域ごとに空間・時間平均（MRA）
- **`output.py` (出力型)**:

  ```python
  from dataclasses import dataclass
  import pandas as pd

  @dataclass(frozen=True)
  class RegionalActivationOutput:
      mra_df: pd.DataFrame  # 列: [subject_id, condition, region_name, mean_activation_na_m]
      region_names: list[str]
  ```

- **`main.py` (エントリー関数)**:
  ```python
  def run_parcellation(
      stc_out: SourceEstimateOutput,
      src_out: AtlasSourceOutput,
      subject_id: str,
      condition: str
  ) -> RegionalActivationOutput:
      ...
  ```
- **単体テスト観点 (`test_main.py`)**:
  - 62領域分の平均活動量（$\text{nA/m}$）を含む `DataFrame` が正しく生成されるか。

---

### Step 5: `step5_stats_visualization`

- **役割**: 条件間の対応のある置換検定（Paired Permutation Test）および 3D 脳活動可視化マップの作成
- **`output.py` (出力型)**:

  ```python
  from dataclasses import dataclass
  from typing import Optional
  import pandas as pd

  @dataclass(frozen=True)
  class StatsVisualizationOutput:
      stats_results_df: pd.DataFrame  # 列: [region_name, diff_mean, p_value, significant]
      figure_output_paths: list[str]
  ```

- **`main.py` (エントリー関数)**:
  ```python
  def run_stats_visualization(
      all_subjects_mra_df: pd.DataFrame,
      condition_a: str,
      condition_b: str,
      output_dir: str
  ) -> StatsVisualizationOutput:
      ...
  ```
- **単体テスト観点 (`test_main.py`)**:
  - 置換検定ロジックがダミーデータに対して期待される p 値・有意判定テーブルを返すか。

---

## 4. 上位層でのオーケストレーション (`exp-reproduce/main.py`)

最上位の `main.py` は各モジュールを順次呼び出し、前段の出力を後段の入力へと渡す責務のみを担います。

```python
"""
exp-reproduce/main.py: 全体パイプライン・オーケストレーション
"""
from modules.step0a_geometry_bem.main import run_geometry_bem
from modules.step0b_atlas_source.main import run_atlas_source
from modules.step0c_forward_model.main import run_forward_model
from modules.step1_preprocessing.main import run_preprocessing
from modules.step2_noise_covariance.main import run_noise_covariance
from modules.step3_source_localization.main import run_source_localization
from modules.step4_parcellation.main import run_parcellation
from modules.step5_stats_visualization.main import run_stats_visualization

def run_pipeline():
    # 1. 共通モデルの準備 (Phase 1)
    bem_out = run_geometry_bem(...)
    src_out = run_atlas_source(bem_out, ...)
    fwd_out = run_forward_model(bem_out, src_out, montage_name="GSN-HydroCel-128")

    # 2. 各被験者・条件の解析 (Phase 2)
    # （例: 被験者ループ & 条件ループ）
    eeg_out = run_preprocessing(raw_eeg_path="...")
    cov_out = run_noise_covariance(eeg_out)
    stc_out = run_source_localization(fwd_out, eeg_out, cov_out)
    mra_out = run_parcellation(stc_out, src_out, subject_id="sub-01", condition="video1")

    # 3. 全体統計検定 & 可視化
    stats_out = run_stats_visualization(all_mra_df, condition_a="rest", condition_b="video1", output_dir="./results")
    print("Pipeline completed successfully!")

if __name__ == "__main__":
    run_pipeline()
```

---

## 5. 単体テストの実行手順

各モジュールは標準の `unittest` で単体テストを実行可能です。

```bash
# 特定のモジュールの単体テストを実行
python -m unittest modules.step1_preprocessing.test_main

# 全モジュールの単体テストを一括実行
python -m unittest discover -s modules -p "test_*.py"
```
