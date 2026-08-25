# Step 0-B: CerebrA変換 & ソース空間作成 実装計画書

## 1. モジュール概要 & 責務
- **モジュール名**: `step0b_atlas_source`
- **対象ディレクトリ**: `exp-reproduce/modules/step0b_atlas_source/`
- **責務**: Step 0-A の FreeSurfer 再構築データに基づき、皮質表面上に約 31,554 点の均等なソース空間グリッド（`mne.SourceSpaces`）を生成する。さらに CerebrA アトラスのラベル画像・CSV から 62 個の大脳皮質領域（`mne.Label` リスト）を抽出し、ソース点との対応関係を確立する。

---

## 2. 利用ライブラリ & 主要 API

| ライブラリ / ツール | 主要モジュール / 関数 | 役割 |
| :--- | :--- | :--- |
| `MNE-Python` | `mne.setup_source_space` | 皮質表面（white/pial）上に `oct-6` 解像度でソース空間グリッドを配置 |
| `MNE-Python` | `mne.read_labels_from_annot` / `mne.Label` | アトラスのアノテーションデータから領域ごとの `Label` オブジェクトを構築 |
| `MNE-Python` | `mne.write_source_spaces` | 生成されたソース空間ファイルの保存 |
| `nibabel` | `nibabel.load` | CerebrA NIfTI 画像から領域 ID ボクセル配列の読み込み |
| `Pandas` | `pd.read_csv` | `CerebrA_LabelDetails.csv` から領域名・ID・半球情報の読み込みとフィルタリング |

---

## 3. データ受け渡し契約 (Interface Contract)

### 3.1 前段からの入力型
- `modules.step0a_geometry_bem.output.GeometryBEMOutput`

### 3.2 内部設定型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class AtlasSourceConfig:
    cerebra_nii_path: str        # CerebrA アトラス NIfTI パス
    cerebra_csv_path: str        # CerebrA ラベル対応表 CSV パス
    spacing: str = "oct6"        # ソース空間グリッド間隔 (oct-6: 約31,554点)
    surface: str = "white"       # 配置基準サーフェス ('white')
    overwrite: bool = False      # 上書きフラグ
```

### 3.3 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
from typing import List
import mne

@dataclass(frozen=True)
class AtlasSourceOutput:
    src: mne.SourceSpaces                  # 定義された皮質ソース空間 (31,554点)
    cerebra_labels: List[mne.Label]       # CerebrA 62皮質領域の Label リスト
    total_sources: int                     # 有効ソース点総数
    src_file_path: str                     # 保存された src.fif のパス
```

### 3.4 関数シグネチャ (`main.py`)
```python
from modules.step0a_geometry_bem.output import GeometryBEMOutput
from .types import AtlasSourceConfig
from .output import AtlasSourceOutput

def run_atlas_source(bem_out: GeometryBEMOutput, config: AtlasSourceConfig) -> AtlasSourceOutput:
    ...
```

---

## 4. 処理フロー & API 呼び出し手順

1. **ソース空間（Source Space）の作成**:
   - `mne.setup_source_space(subject=bem_out.subject_name, spacing=config.spacing, surface=config.surface, subjects_dir=bem_out.subjects_dir, overwrite=config.overwrite)` を実行。
   - 左右半球（lh, rh）の有効頂点数（in-use vertices）の合計が約 31,554 点であることを確認。
2. **CerebrA ラベルメタデータのロード (Pandas)**:
   - `pd.read_csv(config.cerebra_csv_path)` でラベル表をロード。
   - 大脳皮質領域（Cortical regions: 62領域）を抽出し、`Label ID`、`Region Name`、`Hemisphere`（lh/rh）の対応辞書をベクトル的に構築。
3. **CerebrA ボクセルから皮質 Label への変換**:
   - `nibabel.load(config.cerebra_nii_path)` でアトラスボクセルをロード。
   - 各領域 ID に属する皮質頂点インデックスを特定し、`mne.Label(vertices=..., hemi=..., name=..., subject=bem_out.subject_name)` として 62 個の `mne.Label` オブジェクトを生成。
4. **Output DTO の生成と返却**:
   - `src` および 62 個の `cerebra_labels` をカプセル化して `AtlasSourceOutput` を返却。

---

## 5. エラーハンドリング & 境界条件
- **ソース点数の整合性**: `src[0]['nuse'] + src[1]['nuse']` が正の整数であることをアサート。
- **ラベル欠落の防止**: CSV 内の 62 領域すべてに対応する `mne.Label` が生成されているか（`len(cerebra_labels) == 62`）をチェック。空の頂点を持つラベルがある場合は警告をログ。

---

## 6. 単体テスト設計 (`test_main.py`)
- **テストフレームワーク**: `unittest`
- **テストケース 1 (`test_run_atlas_source_structure`)**:
  - モック化された `GeometryBEMOutput` およびダミーの CSV/NIfTI を用いて、`run_atlas_source` が `AtlasSourceOutput` を返し、`src` と `cerebra_labels` の型が一致することを検証。
- **テストケース 2 (`test_label_counts_and_names`)**:
  - 生成された `cerebra_labels` の要素数が 62 個であり、各 Label の `hemi` 属性が `'lh'` または `'rh'` であることを検証。
