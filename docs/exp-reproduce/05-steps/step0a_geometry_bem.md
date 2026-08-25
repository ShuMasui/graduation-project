# Step 0-A: テンプレート幾何再構築 & 3層BEM抽出 実装計画書

## 1. モジュール概要 & 責務
- **モジュール名**: `step0a_geometry_bem`
- **対象ディレクトリ**: `exp-reproduce/modules/step0a_geometry_bem/`
- **責務**: MNI-ICBM152 2009c テンプレート脳の MRI 画像（NIfTI）から、FreeSurfer / MNE-Python を用いて 3層 BEM（皮膚・外頭蓋・内頭蓋）の境界面メッシュを生成し、電気伝導解モデル（`ConductorModel`）を構築・出力する。

---

## 2. 利用ライブラリ & 主要 API

| ライブラリ / ツール | 主要モジュール / 関数 / コマンド | 役割 |
| :--- | :--- | :--- |
| `MNE-Python` | `mne.bem.make_watershed_bem` | MRI から BEM サーフェス（inner_skull, outer_skull, outer_skin）を自動抽出 |
| `MNE-Python` | `mne.make_bem_model` | 抽出したサーフェスと伝導率から BEM 幾何モデルを作成 |
| `MNE-Python` | `mne.make_bem_solution` | BEM 幾何モデルから線形対称境界要素法（BEM）の電気伝導解を計算 |
| `MNE-Python` | `mne.write_bem_surfaces`, `mne.write_bem_solution` | 生成された BEM データの保存 |
| `nibabel` | `nibabel.load` | NIfTI 画像ヘッダおよびアフィン変換行列の検証 |

---

## 3. データ受け渡し契約 (Interface Contract)

### 3.1 入力型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class GeometryBEMConfig:
    template_nii_path: str                          # テンプレート MRI 画像パス (.nii)
    subjects_dir: str                               # FreeSurfer 被験者ディレクトリ
    subject_name: str = "icbm152"                   # 被験者識別名
    conductivity: tuple[float, float, float] = (0.33, 0.0042, 0.33)  # 脳, 頭蓋骨, 皮膚の伝導率 (S/m)
    ico_resolution: int = 4                         # メッシュ解像度 (ico-4: 各面2562頂点)
    overwrite: bool = False                         # 既存ファイルの上書きフラグ
```

### 3.2 出力型 (`output.py`)
```python
from dataclasses import dataclass
import mne

@dataclass(frozen=True)
class GeometryBEMOutput:
    subjects_dir: str                               # FreeSurfer 出力ディレクトリ
    subject_name: str                               # 被験者名 ('icbm152')
    bem_surfaces_path: str                          # BEM サーフェスファイル (*-bem.fif)
    bem_solution: mne.bem.ConductorModel            # 計算済み BEM 電気伝導解モデル
```

### 3.3 関数シグネチャ (`main.py`)
```python
def run_geometry_bem(config: GeometryBEMConfig) -> GeometryBEMOutput:
    ...
```

---

## 4. 処理フロー & API 呼び出し手順

1. **入力検証 & 環境設定**:
   - `config.template_nii_path` の存在確認。
   - `os.environ["SUBJECTS_DIR"] = config.subjects_dir` を設定。
   - すでに計算済みの BEM 解ファイル（`{subjects_dir}/{subject_name}/bem/{subject_name}-5120-bem-sol.fif`）が存在し `config.overwrite=False` の場合は、`mne.read_bem_solution` で即座に読み込んで返す（キャッシュ機構）。
2. **BEM サーフェス抽出**:
   - `mne.bem.make_watershed_bem(subject=config.subject_name, subjects_dir=config.subjects_dir, overwrite=config.overwrite)` を実行。
   - 生成される 3 つのサーフェス（`inner_skull.surf`, `outer_skull.surf`, `outer_skin.surf`）を確認。
3. **BEM 幾何モデルの作成**:
   - `mne.make_bem_model(subject=config.subject_name, ico=config.ico_resolution, conductivity=config.conductivity, subjects_dir=config.subjects_dir)` を呼び出し、BEM サーフェスツリーを取得。
4. **BEM 電気伝導解（ConductorModel）の算出**:
   - `mne.make_bem_solution(bem_surfaces)` を実行し、伝導解マトリックスを生成。
   - `mne.write_bem_solution(..., bem_solution)` でディスクに保存。
5. **Output DTO の生成と返却**:
   - `GeometryBEMOutput` を生成して返却。

---

## 5. エラーハンドリング & 境界条件
- **NIfTI 画像不正**: `template_nii_path` が存在しない場合は `FileNotFoundError` を送出。
- **伝導率の検証**: `config.conductivity` の長さが 3 であり、すべて正の有限値（`> 0`）であることをアサート。
- **事前計算データの流用**: CerebrA 配布物等で事前計算された `bem` サーフェスが存在する場合、再計算をスキップして高速起動する。

---

## 6. 単体テスト設計 (`test_main.py`)
- **テストフレームワーク**: `unittest`
- **テストケース 1 (`test_run_geometry_bem_cached`)**:
  - 事前作成されたダミー BEM 解ファイル（またはモック）を用意し、`run_geometry_bem` が `GeometryBEMOutput` を正常に返すことを検証。
- **テストケース 2 (`test_config_validation`)**:
  - 不正なファイルパスや伝導率を指定した際、適切な例外（`FileNotFoundError`, `ValueError`）が発生することを検証。
