# Step 5: 統計検定 & 8方向3D脳活動可視化 実装仕様書

## 1. モジュール概要 & 責務
- **モジュール名**: `step5_stats_visualization`
- **対象ディレクトリ**: `exp-reproduce/modules/step5_stats_visualization/`
- **責務**: 
  1. 全被験者・全条件の領域活動量データ（Step 4 の結合 DataFrame）を入力として受け取り、条件間（例: Rest vs Video1〜3）の差分について **対応のある置換検定（Paired Permutation Test）** を実行して有意水準（$p < 0.05$）を判定。
  2. CerebrA 62領域の平均活動量（MRA）を皮質表面メッシュ（FreeSurfer 膨張皮質 `lh.inflated`, `rh.inflated` / ソース空間メッシュ）上に投影し、**8方向標準アングル（2×4 グリッド配置）** の高解像度（300 DPI）脳活動推定マップを出力。

---

## 2. 利用ライブラリ & 主要 API

| ライブラリ / ツール | 主要モジュール / 関数 | 役割 |
| :--- | :--- | :--- |
| `NumPy` | `np.random.choice`, `np.mean` | 置換検定（Permutation Test: 10,000回反復）のブロードキャスト・ベクトル化高速検定 |
| `Pandas` | `df.pivot`, `pd.merge` | 被験者ごとの条件間ペア差分行列の構築および結果集約 |
| `Matplotlib` / `Seaborn` | `plt.subplots`, `sns.boxplot` | 統計サマリー図面（条件比較ボックスプロット、差分バープロット、p値ヒストグラム）の描画 |
| `Matplotlib 3D` | `Poly3DCollection`, `Axes3D.view_init` | ヘッドレス環境（DISPLAY不要）での 8方向 3D 脳活動マップ（2×4 統合図面）の高速描画・PNG出力 |
| `MNE-Python` | `mne.read_surface` | FreeSurfer 膨張皮質メッシュ（`lh.inflated`, `rh.inflated`）のロード |

---

## 3. 8方向 脳活動マップの視点・仕様構成

### 3.1 8方向 標準アングル（2×4 グリッド）
| インデックス | 視点名 | 仰角 (`elev`) | 方位角 (`azim`) | 描画対象半球 | 特徴・観察部位 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **Anterior** | 0° | 90° | LH + RH | 正面（前頭極・前頭葉前面） |
| 2 | **Posterior** | 0° | -90° | LH + RH | 背面（後頭極・視覚野背面） |
| 3 | **Superior** | 90° | -90° | LH + RH | 頭頂面（頭頂葉・運動野・体性感覚野） |
| 4 | **Inferior** | -90° | -90° | LH + RH | 底面（側頭葉底面・眼窩前頭皮質） |
| 5 | **Left Lateral** | 0° | 180° | LH のみ | 左 外側面（言語野・左側頭葉・前頭葉外側） |
| 6 | **Right Lateral** | 0° | 0° | RH のみ | 右 外側面（右側頭葉・前頭葉外側） |
| 7 | **Left Medial** | 0° | 0° | LH のみ | 左 内側面（帯状回・楔前部・内側前頭葉） |
| 8 | **Right Medial** | 0° | 180° | RH のみ | 右 内側面（右帯状回・楔前部・内側前頭葉） |

### 3.2 カラーマップ & スケール
- **カラーマップ**: 知覚的一様カラーマップ `viridis`
- **カラースケール**: 解析対象の全被験者・全条件で共通の $[v_{min}, v_{max}]$ を自動算出して適用し、下部に共通カラーバーを配置。
- **出力先**: `results/brain_maps/{subject_id}_{condition}_8views.png` (300 DPI)

---

## 4. データ受け渡し契約 (Interface Contract)

### 4.1 前段からの入力型
- 全被験者・全条件分の Step 4 出力（`RegionalActivationOutput.mra_df`）を縦結合した統合 `pd.DataFrame`
  - 必須列: `['subject_id', 'condition', 'region_name', 'mean_activation_na_m']`

### 4.2 内部設定型 (`types.py`)
```python
from dataclasses import dataclass
from typing import Optional, Any

@dataclass(frozen=True)
class StatsVizConfig:
    condition_a: str                        # 比較基準条件 (例: 'rest')
    condition_b: str                        # 比較対象条件 (例: 'video1')
    n_permutations: int = 10000             # 置換検定の反復回数
    p_threshold: float = 0.05               # 有意水準アルファ
    output_dir: str = "./results"           # 結果ファイル出力先ディレクトリ
    random_state: int = 42                  # 乱数シード
    subjects_dir: Optional[str] = None      # FreeSurfer subjects ディレクトリ
    subject_name: Optional[str] = "icbm152" # テンプレート被験者名
    brain_maps_dir: Optional[str] = None    # 脳マップ保存先ディレクトリ
    src_out: Optional[Any] = None           # Step 0-B の AtlasSourceOutput
    dpi: int = 300                          # 出力解像度
```

### 4.3 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
from typing import List
import pandas as pd

@dataclass(frozen=True)
class StatsVisualizationOutput:
    stats_df: pd.DataFrame                  # 62領域の置換検定統計結果テーブル
    figure_paths: List[str]                 # 生成された図面（統計図 + 8方向脳マップ）のファイルパス一覧
    output_dir: str                         # 保存先ディレクトリ
```

### 4.4 主要関数シグネチャ (`main.py`)
```python
def plot_brain_8views(
    all_subjects_mra_df: pd.DataFrame,
    src_out: Any,
    output_dir: str = "./results",
    subjects_dir: Optional[str] = None,
    subject_name: Optional[str] = "icbm152",
    brain_maps_dir: Optional[str] = None,
    dpi: int = 300
) -> List[str]: ...

def run_stats_visualization(
    all_subjects_mra_df: pd.DataFrame,
    config: StatsVizConfig,
    src_out: Optional[Any] = None
) -> StatsVisualizationOutput: ...
```

---

## 5. 単体テスト設計 (`test_main.py`)
- **テストフレームワーク**: `unittest`
- **テスト項目 (計 10 件)**:
  1. `test_permutation_test_vectorized_p_values`: 置換検定のベクトル化 p 値算出の正確性検証。
  2. `test_stats_dataframe_schema`: `stats_df` の列構成と CSV 出力の検証。
  3. `test_figure_generation_and_paths`: 統計図面（3枚）の生成と存在検証。
  4. `test_missing_columns_raises_error`: 必須列欠損時の例外検証。
  5. `test_no_paired_subjects_raises_error`: ペア被験者不在時の例外検証。
  6. `test_reproducibility_with_seed`: 乱数シード固定による完全再現性検証。
  7. `test_plot_brain_8views_generation`: 8方向脳活動マップの生成と命名規則（`{sub}_{cond}_8views.png`）検証。
  8. `test_run_stats_visualization_with_brain_maps_integration`: `src_out` 連携時の結合出力検証（統計図3枚 + 脳マップ4枚 = 7枚）。
  9. `test_load_surface_mesh_fallback`: FreeSurfer 非存在時の SourceSpace フォールバック堅牢性検証。
  10. `test_map_labels_to_triangles`: CerebrA パーセルから三角形メッシュへのマッピング演算検証。

