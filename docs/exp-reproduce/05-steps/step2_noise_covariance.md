# Step 2: ノイズ共分散 & 動的SNR・正則化パラメータ算出 実装計画書

## 1. モジュール概要 & 責務
- **モジュール名**: `step2_noise_covariance`
- **対象ディレクトリ**: `exp-reproduce/modules/step2_noise_covariance/`
- **責務**: Step 1 の前処理済み EEG データ（`PreprocessedEEGOutput`）から、MNE-Python を用いてノイズ共分散行列（`mne.Covariance`）を計算する。さらに、信号の平均パワーとパワー分散から信号対雑音比（SNR: $\text{dB}$）を算出し、論文手法に従って動的正則化パラメータ $\lambda^2 = \frac{1}{\text{SNR}^2}$ を決定して出力する。

---

## 2. 利用ライブラリ & 主要 API

| ライブラリ / ツール | 主要モジュール / 関数 | 役割 |
| :--- | :--- | :--- |
| `MNE-Python` | `mne.compute_raw_covariance` | 連続 EEG データから経験的ノイズ共分散行列 $C$ を推定 |
| `MNE-Python` | `mne.cov.regularize` | 共分散行列のランク落ち防止のための対角正則化（自動シュリンク） |
| `NumPy` | `np.mean`, `np.var`, `np.log10` | 信号パワーの平均 $P$、分散 $\sigma^2$、および対数 SNR のベクトル化高速計算 |

---

## 3. データ受け渡し契約 (Interface Contract)

### 3.1 前段からの入力型
- `modules.step1_preprocessing.output.PreprocessedEEGOutput`

### 3.2 内部設定型 (`types.py`)
```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class NoiseCovConfig:
    tmin: float = 0.0                       # 共分散計算開始時刻 (秒)
    tmax: Optional[float] = None            # 共分散計算終了時刻 (None = 全区間)
    method: str = "empirical"               # 共分散推定手法 ('empirical' or 'shrunk')
```

### 3.3 公開出力型 (`output.py`)
```python
from dataclasses import dataclass
import mne

@dataclass(frozen=True)
class CovarianceLambdaOutput:
    noise_cov: mne.Covariance               # 計算済みノイズ共分散行列 C
    snr_db: float                           # 算出された信号対雑音比 SNR (dB)
    lambda2: float                          # 動的正則化パラメータ lambda^2 = 1.0 / (SNR^2)
```

### 3.4 関数シグネチャ (`main.py`)
```python
from modules.step1_preprocessing.output import PreprocessedEEGOutput
from .types import NoiseCovConfig
from .output import CovarianceLambdaOutput

def run_noise_covariance(
    eeg_out: PreprocessedEEGOutput,
    config: NoiseCovConfig
) -> CovarianceLambdaOutput:
    ...
```

---

## 4. 処理フロー & API 呼び出し手順

1. **ノイズ共分散行列（$C$）の計算**:
   - `cov = mne.compute_raw_covariance(eeg_out.raw, tmin=config.tmin, tmax=config.tmax, method=config.method)` を実行。
   - `cov = mne.cov.regularize(cov, eeg_out.raw.info, rank=None, proj=True)` で安定化。
2. **NumPy による動的 SNR および $\lambda^2$ のベクトル化計算**:
   - データ配列 $X \in \mathbb{R}^{N_{ch} \times N_{samples}}$ を `eeg_out.raw.get_data()` で取得。
   - 各時刻における全電極の瞬時パワー $p(t) = \frac{1}{N_{ch}} \sum_{i=1}^{N_{ch}} X_{i,t}^2$ をベクトル計算:
     ```python
     signal_power = np.mean(data ** 2, axis=0)  # 時系列瞬時パワー (1D array)
     p_mean = np.mean(signal_power)             # 平均パワー P
     sigma2 = np.var(signal_power)              # パワーの分散 sigma^2
     ```
   - 論文の定義式（式1）に基づき SNR を算出:
     $$\text{SNR} = 10 \cdot \log_{10}\left(\frac{P}{\sigma^2}\right)$$
   - 正則化パラメータ $\lambda^2$ を決定:
     $$\lambda^2 = \frac{1}{\text{SNR}^2}$$
3. **Output DTO の生成と返却**:
   - `CovarianceLambdaOutput(noise_cov=cov, snr_db=float(snr), lambda2=float(lambda2))` を返却。

---

## 5. エラーハンドリング & 境界条件
- **ゼロ除算・非正値防止**: $\sigma^2 \le 0$ または $\text{SNR} \le 0$ の場合（極度の無音・異常信号）は、最小クリップ値（$\text{SNR} = 1.0 \implies \lambda^2 = 1.0$）をフォールバックとして適用。
- **for ループの排除**: パワー計算において一切 Python の `for` ループを使用せず、NumPy の `axis=0` によるブロードキャスト集約を行う。

---

## 6. 単体テスト設計 (`test_main.py`)
- **テストフレームワーク**: `unittest`
- **テストケース 1 (`test_compute_snr_and_lambda2_math`)**:
  - 既知の分散と平均を持つダミーデータを作成し、NumPy の計算結果が数式通りの SNR および $\lambda^2$ と厳密に一致することを検証。
- **テストケース 2 (`test_noise_cov_output_contract`)**:
  - `CovarianceLambdaOutput` の `noise_cov` が `mne.Covariance` インスタンスであり、`lambda2` が正の有限実数であることを検証。
