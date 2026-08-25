# Step 1: 生EEGデータ前処理 実装計画書

## 1. モジュール概要 & 責務
- **モジュール名**: `step1_preprocessing`
- **対象ディレクトリ**: `exp-reproduce/modules/step1_preprocessing/`
- **責務**: 生の高密度 EEG データ（500 Hz）を取り込み、ダウンサンプリング（125 Hz）、バンドパスフィルタ（1.0〜50.0 Hz）、PREP パイプラインによる異常チャンネル検出・補間およびロバスト平均再参照、FastICA による眼球運動・筋電アーティファクトの自動同定・除去を行い、クリーンな連続 Raw オブジェクト（`mne.io.Raw`）を出力する。

---

## 2. 利用ライブラリ & 主要 API

| ライブラリ / ツール | 主要モジュール / 関数 | 役割 |
| :--- | :--- | :--- |
| `MNE-Python` | `mne.io.read_raw_fif` / `mne.io.read_raw_egi` / `mne.io.read_raw_brainvision` | 様々な形式の生 EEG データをロード |
| `MNE-Python` | `raw.resample` | サンプリングレートを 125 Hz にダウンサンプリング（アンチエイリアシング適用） |
| `MNE-Python` | `raw.filter` | 1.0 〜 50.0 Hz の FIR バンドパスフィルタ（ゼロ位相歪み） |
| `pyprep` | `pyprep.PrepPipeline` | 異常電極（Bad Channels）のロバスト検出と球面スプライン補間、電源ノイズ除去、平均再参照 |
| `MNE-Python` | `mne.preprocessing.ICA` | FastICA アルゴリズムによる独立成分分析 |
| `MNE-Python` | `ica.find_bads_eog` / `ica.apply` | EOG 参照電極または相関分析による瞬き成分の同定と除去 |

---

## 3. データ受け渡し契約 (Interface Contract)

### 3.1 内部設定型 (`types.py`)
```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class PreprocessingConfig:
    raw_eeg_path: str                       # 入力生EEGデータファイルパス
    target_sampling_rate: float = 125.0     # 目標サンプリング周波数 (Hz)
    l_freq: float = 1.0                     # バンドパス下限周波数 (Hz)
    h_freq: float = 50.0                    # バンドパス上限周波数 (Hz)
    apply_prep: bool = True                 # PREP パイプライン適用の有無
    ica_n_components: int = 20              # ICA 分解成分数
    random_state: int = 42                  # 再現性のための乱数シード
```

### 3.2 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
from typing import List
import mne

@dataclass(frozen=True)
class PreprocessedEEGOutput:
    raw: mne.io.BaseRaw                     # 前処理済みクリーン Raw データ
    sampling_rate: float                    # 適用後サンプリングレート (125.0 Hz)
    bad_channels: List[str]                 # 検出・補間された不良電極名リスト
    removed_ica_components: List[int]       # 除去されたノイズ ICA 成分インデックス
```

### 3.3 関数シグネチャ (`main.py`)
```python
from .types import PreprocessingConfig
from .output import PreprocessedEEGOutput

def run_preprocessing(config: PreprocessingConfig) -> PreprocessedEEGOutput:
    ...
```

---

## 4. 処理フロー & API 呼び出し手順

1. **生 EEG データのロード**:
   - ファイル拡張子（`.fif`, `.mff`, `.raw`, `.vhdr`）に応じて適切な `mne.io.read_raw_*` を自動選択し、`preload=True` でロード。
2. **ダウンサンプリング**:
   - `raw.resample(sfreq=config.target_sampling_rate, npad="auto")` を実行（500 Hz $\rightarrow$ 125 Hz）。
3. **バンドパスフィルタの適用**:
   - `raw.filter(l_freq=config.l_freq, h_freq=config.h_freq, phase='zero', fir_design='firwin')` を適用。
4. **PREP による Bad Channel 補間 & 再参照**:
   - `config.apply_prep=True` の場合、`pyprep.PrepPipeline` を実行。異常電極を `raw.info['bads']` に登録し、`raw.interpolate_bads(reset_bads=True)` で球面スプライン補間を実施後、平均再参照（`raw.set_eeg_reference('average')`）を適用。
5. **ICA によるアーティファクト除去**:
   - `ica = mne.preprocessing.ICA(n_components=config.ica_n_components, method='fastica', random_state=config.random_state)`
   - `ica.fit(raw)` を実行。
   - 眼球運動相関成分を自動検出し、`ica.exclude = bad_eog_indices` を設定。
   - `cleaned_raw = ica.apply(raw.copy())` でノイズ成分を差し引いた信号を復元。
6. **Output DTO の生成と返却**:
   - `PreprocessedEEGOutput` を生成して返却。

---

## 5. エラーハンドリング & 境界条件
- **サンプリングレートの検証**: 既に 125 Hz 以下のデータが入力された場合はダウンサンプリングをスキップ。
- **ICA 収束失敗**: FastICA が規定回数で収束しない場合は最大反復回数（`max_iter`）を増やしてリトライ。

---

## 6. 単体テスト設計 (`test_main.py`)
- **テストフレームワーク**: `unittest`
- **テストケース 1 (`test_run_preprocessing_synthetic`)**:
  - `mne.io.RawArray` で作成した正弦波＋ノイズの合成 EEG データ（500 Hz, 64ch）に対して `run_preprocessing` を実行し、出力サンプリングレートが 125 Hz になり、周波数帯域が 1-50 Hz 内に収まっていることを検証。
- **テストケース 2 (`test_output_types_and_immutability`)**:
  - 返却されるオブジェクトが `PreprocessedEEGOutput` であり、各フィールド（`bad_channels`, `removed_ica_components`）が期待される型であることを検証。
