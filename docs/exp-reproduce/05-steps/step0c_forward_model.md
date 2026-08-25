# Step 0-C: 電極共登録 & 順モデル一括計算 実装計画書

## 1. モジュール概要 & 責務
- **モジュール名**: `step0c_forward_model`
- **対象ディレクトリ**: `exp-reproduce/modules/step0c_forward_model/`
- **責務**: 高密度 EEG 電極モンタージュ（128ch EGI または 64ch ActiCap）を標準脳頭皮メッシュに共登録（Co-registration: 座標変換行列 `trans` の作成）し、BEM 電気伝導モデルおよびソース空間と結合して全被験者共通の順モデル（Lead Field 行列 `mne.Forward`）を一括事前計算する。

---

## 2. 利用ライブラリ & 主要 API

| ライブラリ / ツール | 主要モジュール / 関数 | 役割 |
| :--- | :--- | :--- |
| `MNE-Python` | `mne.channels.make_standard_montage` | 標準電極配置（例: `GSN-HydroCel-128`）の 3D 座標をロード |
| `MNE-Python` | `mne.create_info` | 電極名・サンプリング周波数・チャンネル種別（EEG）を持つ `mne.Info` を生成 |
| `MNE-Python` | `mne.transforms.Transform` / `mne.coreg.fit_matched_points` | 解剖基準点（Nasion, LPA, RPA）に基づき Head 座標系から MRI 座標系への変換行列 `trans` を作成 |
| `MNE-Python` | `mne.make_forward_solution` | BEM 解、ソース空間、共登録電極からリードフィールド行列（順解）を一括計算 |
| `MNE-Python` | `mne.write_forward_solution` | 順モデルファイル (`fwd.fif`) の保存 |

---

## 3. データ受け渡し契約 (Interface Contract)

### 3.1 前段からの入力型
- `modules.step0a_geometry_bem.output.GeometryBEMOutput`
- `modules.step0b_atlas_source.output.AtlasSourceOutput`

### 3.2 内部設定型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ForwardModelConfig:
    montage_name: str = "GSN-HydroCel-128" # 電極配置名 ('GSN-HydroCel-128' or 'standard_64')
    eeg_channels_count: int = 128          # 電極数
    mindist: float = 5.0                   # 内頭蓋骨面からの最小距離 (mm)
    n_jobs: int = 1                        # 並列処理プロセス数
    overwrite: bool = False                # 上書きフラグ
```

### 3.3 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
import mne

@dataclass(frozen=True)
class ForwardModelOutput:
    forward: mne.Forward                   # 順モデル / Lead Field 行列 (128ch x 31554 sources)
    trans: mne.transforms.Transform        # 電極-頭部座標変換マトリックス
    info: mne.Info                         # 電極位置メタ情報
    fwd_file_path: str                     # 保存された fwd.fif のパス
```

### 3.4 関数シグネチャ (`main.py`)
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
    ...
```

---

## 4. 処理フロー & API 呼び出し手順

1. **電極モンタージュの取得 & Info 作成**:
   - `montage = mne.channels.make_standard_montage(config.montage_name)` で電極座標を取得。
   - `ch_names = montage.ch_names[:config.eeg_channels_count]`
   - `info = mne.create_info(ch_names=ch_names, sfreq=125.0, ch_types='eeg')` を作成し、`info.set_montage(montage)` を適用。
2. **座標変換行列（`trans`）の自動アライメント**:
   - テンプレート頭部モデルの Fiducials（Nasion, LPA, RPA）とモンタージュの基準点を一致させるアフィン変換行列（`mne.transforms.Transform("head", "mri", ...)`）を生成。
3. **順モデル（Lead Field 行列）の計算**:
   - `fwd = mne.make_forward_solution(info=info, trans=trans, src=src_out.src, bem=bem_out.bem_solution, eeg=True, meg=False, mindist=config.mindist, n_jobs=config.n_jobs)` を実行。
   - リードフィールド行列のサイズ（`fwd['sol']['data'].shape` == `(128, 31554 * 3)` 等）を検証。
4. **ディスク保存 & Output DTO 生成**:
   - `mne.write_forward_solution(..., fwd, overwrite=config.overwrite)` で保存。
   - `ForwardModelOutput` を生成して返却。

---

## 5. エラーハンドリング & 境界条件
- **電極数の不一致**: モンタージュ内の電極数と `config.eeg_channels_count` が整合しているかを事前検証。
- **BEM 領域外のソース点**: `mindist` により内頭蓋骨に近すぎるソース点が自動除外される際の警告ログを適切にハンドリング。

---

## 6. 単体テスト設計 (`test_main.py`)
- **テストフレームワーク**: `unittest`
- **テストケース 1 (`test_run_forward_model_shape`)**:
  - モックの BEM 解およびソース空間を用いて `run_forward_model` を実行し、生成された `forward` オブジェクトが EEG チャンネル数とソース点数を正しく保持していることを検証。
- **テストケース 2 (`test_trans_identity_or_fitted`)**:
  - `trans` 変換行列が 4x4 の正方行列であり、`from` が `head`、`to` が `mri` であることを検証。
