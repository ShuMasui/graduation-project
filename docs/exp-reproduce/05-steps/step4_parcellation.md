# Step 4: CerebrA 領域集約 (MRA算出) 実装計画書

## 1. モジュール概要 & 責務
- **モジュール名**: `step4_parcellation`
- **対象ディレクトリ**: `exp-reproduce/modules/step4_parcellation/`
- **責務**: Step 3 のソース空間推定結果（`SourceEstimateOutput`）と Step 0-B の CerebrA 領域定義（`AtlasSourceOutput`）を受け取り、MNE-Python のラベル時系列抽出機能および Pandas を用いて、大脳皮質 62 領域ごとの時間・空間平均活動量（Mean Regional Activation: MRA, 単位 $\text{nA/m}$）をベクトル集約して構造化 DataFrame として出力する。

---

## 2. 利用ライブラリ & 主要 API

| ライブラリ / ツール | 主要モジュール / 関数 | 役割 |
| :--- | :--- | :--- |
| `MNE-Python` | `mne.extract_label_time_course` | ソース空間推定値 `stc` を 62 個の `mne.Label` 領域ごとに空間平均抽出（`mode='mean'`） |
| `NumPy` | `np.mean` | 各領域の時系列データから時間軸平均をベクトル的に一括計算 |
| `Pandas` | `pd.DataFrame` | 集約された 62 領域の MRA 値を、被験者 ID・条件名・領域名を付与した整然データ（Tidy Data）として構造化 |

---

## 3. データ受け渡し契約 (Interface Contract)

### 3.1 前段からの入力型
- `modules.step0b_atlas_source.output.AtlasSourceOutput`
- `modules.step3_source_localization.output.SourceEstimateOutput`

### 3.2 内部メタデータ型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SubjectMetadata:
    subject_id: str                         # 被験者ID (例: 'sub-01')
    condition: str                          # 実験条件 (例: 'rest', 'video1', 'video2')
    extract_mode: str = "mean"              # ラベル内空間集約方式 ('mean')
```

### 3.3 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
from typing import List
import pandas as pd

@dataclass(frozen=True)
class RegionalActivationOutput:
    # mra_df 列: ['subject_id', 'condition', 'region_name', 'mean_activation_na_m']
    mra_df: pd.DataFrame                   # 62領域の MRA データフレーム (62行 x 4列)
    region_names: List[str]                # 62個の皮質領域名リスト
```

### 3.4 関数シグネチャ (`main.py`)
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
    ...
```

---

## 4. 処理フロー & API 呼び出し手順

1. **領域別時系列の抽出 (空間集約)**:
   - `label_tc = mne.extract_label_time_course(stcs=stc_out.stc, labels=src_out.cerebra_labels, src=src_out.src, mode=metadata.extract_mode, verbose=False)` を実行。
   - `label_tc` は形状 `(62, N_times)` の 2D NumPy 配列となる。
2. **時間平均活動量（MRA）のベクトル算出**:
   - `for` 文を一切回さず、NumPy の `axis=1` で時間軸平均を一括計算:
     ```python
     # 62領域の平均活動量 (nA/m)
     mra_values = np.mean(label_tc, axis=1)  # shape: (62,)
     ```
3. **Pandas 整然データフレームの構築**:
   - 領域名リスト `region_names = [label.name for label in src_out.cerebra_labels]` を取得。
   - `pd.DataFrame` をベクトル的に作成:
     ```python
     mra_df = pd.DataFrame({
         "subject_id": metadata.subject_id,
         "condition": metadata.condition,
         "region_name": region_names,
         "mean_activation_na_m": mra_values
     })
     ```
4. **Output DTO の生成と返却**:
   - `RegionalActivationOutput(mra_df=mra_df, region_names=region_names)` を返却。

---

## 5. エラーハンドリング & 境界条件
- **領域数の整合性**: `mra_df` の行数が `len(src_out.cerebra_labels)`（62行）と厳密に一致することを検証。
- **NaN / Inf の排除**: 計算された MRA 値に `NaN` または `Inf` が含まれていないことを `mra_df.isna().sum().sum() == 0` でアサート。

---

## 6. 単体テスト設計 (`test_main.py`)
- **テストフレームワーク**: `unittest`
- **テストケース 1 (`test_parcellation_vectorized_shape`)**:
  - モックの `SourceEstimate`（62領域、100タイムポイント）とダミーラベルを用いて `run_parcellation` を実行し、生成される `mra_df` が 62 行であり、期待される列名を持つことを検証。
- **テストケース 2 (`test_mra_non_negative_values`)**:
  - 推定された電流密度ノルムの平均値がすべて非負（$\ge 0$）であることを検証。
