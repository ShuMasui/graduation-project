# Step 3: eLORETA 音源推定 実装計画書

## 1. モジュール概要 & 責務
- **モジュール名**: `step3_source_localization`
- **対象ディレクトリ**: `exp-reproduce/modules/step3_source_localization/`
- **責務**: Step 0-C の共通順モデル（`ForwardModelOutput`）、Step 1 の前処理済み EEG（`PreprocessedEEGOutput`）、および Step 2 のノイズ共分散・適応的正則化パラメータ（`CovarianceLambdaOutput`）を結合し、MNE-Python の逆作用素を作成して **eLORETA アルゴリズム** により脳内各ソース点（約 31,554 点）の時系列電流密度（$\text{nA/m}$）を推定・出力する。

---

## 2. 利用ライブラリ & 主要 API

| ライブラリ / ツール | 主要モジュール / 関数 | 役割 |
| :--- | :--- | :--- |
| `MNE-Python` | `mne.minimum_norm.make_inverse_operator` | 順モデル $L$ とノイズ共分散 $C$ から逆作用素（InverseOperator）を生成 |
| `MNE-Python` | `mne.minimum_norm.apply_inverse_raw` | 連続 EEG データに対して `method='eLORETA'` および `lambda2` を適用し、時系列音源推定（`mne.SourceEstimate`）を算出 |

---

## 3. データ受け渡し契約 (Interface Contract)

### 3.1 前段からの入力型
- `modules.step0c_forward_model.output.ForwardModelOutput`
- `modules.step1_preprocessing.output.PreprocessedEEGOutput`
- `modules.step2_noise_covariance.output.CovarianceLambdaOutput`

### 3.2 内部設定型 (`types.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SourceLocConfig:
    method: str = "eLORETA"                 # 逆問題ソルバー名 ('eLORETA')
    loose: float = 0.2                      # 双極子の法線方向拘束 (0.2: loose orientation)
    depth: float = 0.8                      # 深度重み付けパラメータ (0.8)
    pick_ori: str | None = None             # 双極子モーメントの向き ('vector' or None = 法線ノルム)
    prepared: bool = True                   # 逆作用素の事前準備フラグ
```

### 3.3 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
import mne

@dataclass(frozen=True)
class SourceEstimateOutput:
    stc: mne.SourceEstimate                # 推定されたソース空間時系列電流密度 (nA/m)
    method: str                            # 適用手法 ('eLORETA')
    lambda2_used: float                    # 適用された正則化パラメータ
```

### 3.4 関数シグネチャ (`main.py`)
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
    ...
```

---

## 4. 処理フロー & API 呼び出し手順

1. **逆作用素（Inverse Operator）の構築**:
   - `inv_op = mne.minimum_norm.make_inverse_operator(info=eeg_out.raw.info, forward=fwd_out.forward, noise_cov=cov_out.noise_cov, loose=config.loose, depth=config.depth, fixed=False)` を実行。
   - 逆作用素に eLORETA 用の事前重み行列が構築されていることを確認。
2. **eLORETA による音源推定の適用**:
   - `stc = mne.minimum_norm.apply_inverse_raw(raw=eeg_out.raw, inverse_operator=inv_op, lambda2=cov_out.lambda2, method=config.method, pick_ori=config.pick_ori, prepared=config.prepared)` を実行。
   - 得られた `stc.data` の形状が `(31554, N_times)` であり、値が電流密度（$\text{nA/m}$）であることを検証。
3. **Output DTO の生成と返却**:
   - `SourceEstimateOutput(stc=stc, method=config.method, lambda2_used=cov_out.lambda2)` を生成して返却。

---

## 5. エラーハンドリング & 境界条件
- **電極名の整合性**: `eeg_out.raw.info['ch_names']` と `fwd_out.forward['info']['ch_names']` に共通する電極数が十分（90% 以上）存在するかを検証。
- **次元の不一致防止**: MNE の内部ルーチンにより自動的に共通チャンネル集合で射影が行われることを確認。

---

## 6. 単体テスト設計 (`test_main.py`)
- **テストフレームワーク**: `unittest`
- **テストケース 1 (`test_apply_eloreta_synthetic`)**:
  - 小型モック順モデル（16ch $\times$ 100 sources）とモック Raw データを用いて `run_source_localization` を実行し、生成された `stc` の時間長が Raw データと一致し、全値が有限実数であることを検証。
- **テストケース 2 (`test_output_contract_fields`)**:
  - `SourceEstimateOutput` の各フィールド（`stc`, `method`, `lambda2_used`）が型定義と一致することを検証。
