# Step 5: 統計検定 & 3D脳活動可視化 実装計画書

## 1. モジュール概要 & 責務
- **モジュール名**: `step5_stats_visualization`
- **対象ディレクトリ**: `exp-reproduce/modules/step5_stats_visualization/`
- **責務**: 全被験者・全条件の領域活動量データ（Step 4 の結合 DataFrame）を入力として受け取り、条件間（例: Rest vs Video1〜3）の差分について **対応のある置換検定（Paired Permutation Test）** を実行して有意水準（$p < 0.05$）を判定する。さらに、有意な領域活動差を 3D 脳表面（Open3D / Matplotlib）上にカラーマップ投影し、論文と同等の解析結果図・統計テーブルを出力する。

---

## 2. 利用ライブラリ & 主要 API

| ライブラリ / ツール | 主要モジュール / 関数 | 役割 |
| :--- | :--- | :--- |
| `NumPy` | `np.random.choice`, `np.mean` | 置換検定（Permutation Test: 10,000回反復）のブロードキャスト・ベクトル化高速検定 |
| `Pandas` | `df.pivot`, `pd.merge` | 被験者ごとの条件間ペア差分行列の構築および結果集約 |
| `SciPy` | `scipy.stats` | 基本統計量（平均、標準偏差、効果量 Cohen's d）の算出 |
| `Matplotlib` / `Seaborn` | `plt.subplots`, `sns.boxplot` | 論文 Figure 4（条件別活動量ボックスプロット）および Figure 5（置換分布ヒストグラム）の描画 |
| `Open3D` (または `MNE-Python` 3Dプロット) | `open3d.visualization`, `stc.plot` | 論文 Figure 6 / 7（3D 大脳皮質上での活動差カラーマップ）の描画・画像保存 |

---

## 3. データ受け渡し契約 (Interface Contract)

### 3.1 前段からの入力型
- 全被験者・全条件分の Step 4 出力（`RegionalActivationOutput.mra_df`）を縦結合した統合 `pd.DataFrame`
  - 必須列: `['subject_id', 'condition', 'region_name', 'mean_activation_na_m']`

### 3.2 内部設定型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class StatsVizConfig:
    condition_a: str                        # 比較基準条件 (例: 'rest')
    condition_b: str                        # 比較対象条件 (例: 'video1' または 'video_avg')
    n_permutations: int = 10000             # 置換検定の反復回数
    p_threshold: float = 0.05               # 有意水準アルファ
    output_dir: str = "./results"           # 結果ファイル出力先ディレクトリ
    random_state: int = 42                  # 乱数シード
```

### 3.3 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
from typing import List
import pandas as pd

@dataclass(frozen=True)
class StatsVisualizationOutput:
    # stats_df 列: ['region_name', 'mean_a', 'mean_b', 'mean_diff', 'p_value', 'significant']
    stats_df: pd.DataFrame                  # 62領域の置換検定統計結果テーブル
    figure_paths: List[str]                 # 生成された図面（ボックスプロット、3Dマップ）のファイルパス一覧
    output_dir: str                         # 保存先ディレクトリ
```

### 3.4 関数シグネチャ (`main.py`)
```python
import pandas as pd
from .types import StatsVizConfig
from .output import StatsVisualizationOutput

def run_stats_visualization(
    all_subjects_mra_df: pd.DataFrame,
    config: StatsVizConfig
) -> StatsVisualizationOutput:
    ...
```

---

## 4. 処理フロー & API 呼び出し手順

1. **ペアデータセットの整形 (Pandas ピボット)**:
   - `df_pivot = all_subjects_mra_df.pivot(index=['subject_id', 'region_name'], columns='condition', values='mean_activation_na_m')`
   - 各被験者・各領域におけるペア差分ベクトル $D = X_B - X_A \in \mathbb{R}^{N_{sub} \times 62}$ を一括計算。
2. **ベクトル化置換検定（Paired Permutation Test）**:
   - `for` 文による逐次検定を避け、NumPy の乱数符号行列 $S \in \{-1, +1\}^{N_{perm} \times N_{sub} \times 1}$ を生成:
     ```python
     # 観測平均差 (shape: 62,)
     observed_diff = np.mean(diff_matrix, axis=0)
     
     # 10,000回の符号反転ブロードキャスト (shape: 10000, 62)
     signs = np.random.choice([-1, 1], size=(config.n_permutations, n_subjects, 1))
     perm_diffs = np.mean(signs * diff_matrix[np.newaxis, :, :], axis=1)
     
     # 2側検定 p値のベクトル計算
     p_values = np.mean(np.abs(perm_diffs) >= np.abs(observed_diff), axis=0)
     ```
3. **結果テーブルの構築**:
   - `significant = p_values < config.p_threshold` を判定し、整然 DataFrame（`stats_df`）を作成して CSV 保存。
4. **可視化プロットの生成 (Matplotlib / 3D)**:
   - **Figure A**: 条件別活動量のボックスプロット (`sns.boxplot`) を作成・保存。
   - **Figure B**: 62 領域の有意な差分値（非有意は 0 にマスク）をカラーマップ化し、大脳皮質 3D モデルに投影して PNG 保存。
5. **Output DTO の生成と返却**:
   - `StatsVisualizationOutput(stats_df=stats_df, figure_paths=[...], output_dir=config.output_dir)` を返却。

---

## 5. エラーハンドリング & 境界条件
- **被験者ペアの欠損チェック**: 条件 A と 条件 B の両方にデータが存在しない被験者を事前に自動除外。
- **再現性の保証**: `np.random.seed(config.random_state)` により置換検定の p 値が完全に再現可能であることを担保。

---

## 6. 単体テスト設計 (`test_main.py`)
- **テストフレームワーク**: `unittest`
- **テストケース 1 (`test_permutation_test_vectorized_p_values`)**:
  - 条件 B の活動量が条件 A より明らかに高いダミーデータ（10被験者分）を作成し、置換検定の p 値が $p < 0.01$ となり有意と判定されることを検証。
- **テストケース 2 (`test_stats_dataframe_schema`)**:
  - `stats_df` が 62 行であり、必要な全列（`region_name`, `mean_diff`, `p_value`, `significant`）を含んでいることを検証。
