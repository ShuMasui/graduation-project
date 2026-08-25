# 高密度EEG解析処理フロー設計書 (Processing Flow)

本ドキュメントは、高密度EEG（High-Density EEG）データを対象とした、標準脳テンプレート（MNI-ICBM 2009c）および CerebrA アトラスに基づく音源推定（eLORETA）・領域解析パイプラインの処理フロー、利用ライブラリ、および各ステップの入出力関係を定義したものです。

---

## 1. パイプライン全体アーキテクチャ

パイプラインは、全被験者共通の幾何モデルを作成する **「Phase 1: 事前準備フェーズ」** と、被験者・条件ごとの生EEGデータを処理する **「Phase 2: データ解析フェーズ」** の2段階で構成されます。

```mermaid
flowchart TD
    subgraph Phase 1: 事前準備フェーズ（共通モデルの構築）
        P1["Step 0-A: テンプレート幾何再構築<br>【FreeSurfer, nibabel】"] -->|"出力: メッシュ & 3層BEM"| P2["Step 0-B: アトラス変換 & ソース空間作成<br>【cerebra_atlas_python, MNE-Python】"]
        P1 -->|"出力: BEMモデル"| P3["Step 0-C: 電極共登録 & 順モデル計算<br>【MNE-Python】"]
        P2 -->|"出力: ソース空間 src & ラベル"| P3
    end

    subgraph Phase 2: データ解析フェーズ（被験者・試行ごとの処理）
        E1["Step 1: 生EEG前処理<br>【MNE-Python, pyprep】"] -->|"出力: クリーンEEG raw"| E2["Step 2: ノイズ共分散 & 動的SNR計算<br>【NumPy, MNE-Python】"]
        E1 -->|"出力: クリーンEEG raw"| E3["Step 3: eLORETA 音源推定<br>【MNE-Python】"]
        E2 -->|"出力: noise_cov, lambda2"| E3
        P3 -.->|"入力: 順モデル fwd"| E3
        
        E3 -->|"出力: ソース推定 stc"| E4["Step 4: CerebrA領域集約 (MRA)<br>【MNE-Python, Pandas】"]
        P2 -.->|"入力: CerebrAラベル"| E4
        
        E4 -->|"出力: 62領域活動量テーブル"| E5["Step 5: 置換検定 & 3D可視化<br>【SciPy, Matplotlib, Open3D】"]
    end
```

---

## 2. Phase 1: 事前準備フェーズ（共通モデルの構築）

個別MRIが存在しない環境に対応するため、全被験者共通で使用する順モデル（Lead Field行列）および解剖学的アトラス定義をあらかじめ作成します。

### Step 0-A: テンプレート脳の幾何再構築 & BEM境界面の抽出
* **担当ライブラリ / ツール**: `FreeSurfer` (`recon-all`, `mri_watershed`), `nibabel`
* **期待入力**:
  - 標準脳 MRI 画像 (`mni_icbm152_t1_tal_nlin_sym_09c.nii`)
* **処理内容**:
  1. MRI 画像から大脳皮質の白質面（White matter surface）および軟膜面（Pial surface）を再構築。
  2. Watershed アルゴリズムを用いて頭部3層（外皮膚: Skin, 頭蓋骨外側: Outer Skull, 頭蓋骨内側: Inner Skull）の境界メッシュを生成。
* **期待出力**:
  - FreeSurfer 被験者再構築ディレクトリ (`subjects_dir/icbm152/`)
  - 3層 BEM サーフェスファイル (`*-bem.surf` / `*-bem-sol.fif`)

---

### Step 0-B: CerebrA アトラスの変換とソース空間の作成
* **担当ライブラリ**: `cerebra_atlas_python`, `MNE-Python` (`mne.setup_source_space`), `nibabel`
* **期待入力**:
  1. Step 0-A の FreeSurfer 再構築ディレクトリ
  2. CerebrA アトラスの NIfTI ラベル画像 (`CerebrA.nii`)
* **処理内容**:
  1. CerebrA のボクセルラベルを FreeSurfer 座標系へアライメント・変換。
  2. 大脳皮質メッシュ上に均等な約 31,554 点の双極子グリッド（ソース空間 `src`）を定義。
  3. 各ソース点と CerebrA の 62 個の大脳皮質領域ラベルを紐付け。
* **期待出力**:
  - ソース空間定義オブジェクト (`src` / `src.fif`)
  - CerebrA 皮質ラベルリスト (`cerebra_labels` / 62領域の `mne.Label` オブジェクト群)

---

### Step 0-C: 電極共登録 (Co-registration) & 順モデル (Lead Field) の事前計算
* **担当ライブラリ**: `MNE-Python` (`mne.channels`, `mne.make_bem_solution`, `mne.make_forward_solution`)
* **期待入力**:
  1. Step 0-A の 3層 BEM 伝導解モデル (`bem_sol`)
  2. Step 0-B の ソース空間 (`src`)
  3. 高密度電極モンタージュ座標（128ch EGI GSN または 64ch ActiCap の 3D 座標）
  4. 解剖学的基準点（Fiducials: Nasion, LPA, RPA）
* **処理内容**:
  1. 電極位置をテンプレート頭皮メッシュの基準点に合わせて平行移動・回転・スケーリング（座標変換行列 `trans` の作成）。
  2. BEM 伝導解モデル、ソース空間、および共登録された電極配置から、リードフィールド行列（順解）を一括計算。
* **期待出力**:
  - 共通順モデルオブジェクト (`fwd` / `fwd.fif`)

---

## 3. Phase 2: データ解析フェーズ（被験者・試行ごとの処理）

各被験者の生EEGデータを前処理し、Phase 1 で作成した順モデルを用いて音源推定・領域集約・統計検定を行います。

### Step 1: 生 EEG データの前処理 (Pre-processing)
* **担当ライブラリ**: `MNE-Python` (`mne.io`, `mne.filter`, `mne.preprocessing.ICA`), `pyprep`
* **期待入力**:
  - 生の高密度 EEG データファイル（サンプリングレート 500 Hz、EGI `.mff` / `.raw` や BrainVision `.vhdr` 等）
* **処理内容**:
  1. **ダウンサンプリング**: 500 Hz $\rightarrow$ 125 Hz (`raw.resample(125)`)
  2. **バンドパスフィルタ**: 1.0 〜 50.0 Hz (`raw.filter(1.0, 50.0)`)
  3. **PREP パイプライン**: 異常チャンネル（Bad Channels）の検出と球面スプライン補間、商用電源ノイズ除去、ロバスト平均再参照
  4. **FastICA**: 独立成分分析を実行し、眼球運動（瞬き）・筋電・心電ノイズ成分を自動同定して除去 (`ica.apply()`)
* **期待出力**:
  - アーティファクトが除去されたクリーンな連続 EEG データ (`cleaned_raw` / `mne.io.Raw`)

---

### Step 2: ノイズ共分散行列と動的正則化パラメータ ($\lambda^2$) の算出
* **担当ライブラリ**: `MNE-Python` (`mne.compute_raw_covariance`), `NumPy`
* **期待入力**:
  - Step 1 のクリーン EEG データ (`cleaned_raw`)
* **処理内容**:
  1. 連続データ区間からノイズ共分散行列 $C$ を推定 (`mne.compute_raw_covariance`)。
  2. 信号の平均パワー $P$ とパワー分散 $\sigma^2$ から $\text{SNR} = 10 \log_{10}(P/\sigma^2)$ を算出。
  3. 正則化パラメータ $\lambda^2 = 1 / \text{SNR}^2$ を動的に決定（信号品質に適応）。
* **期待出力**:
  - ノイズ共分散行列 (`noise_cov` / `mne.Covariance`)
  - 動的正則化パラメータ (`lambda2` / `float`)

---

### Step 3: 逆作用素の作成と eLORETA 音源推定 (Inverse Solution)
* **担当ライブラリ**: `MNE-Python` (`mne.minimum_norm.make_inverse_operator`, `mne.minimum_norm.apply_inverse_raw`)
* **期待入力**:
  1. Step 0-C の順モデル (`fwd`)
  2. Step 1 のクリーン EEG データ (`cleaned_raw`)
  3. Step 2 の ノイズ共分散 (`noise_cov`) および 正則化パラメータ (`lambda2`)
* **処理内容**:
  1. 順モデルとノイズ共分散から逆作用素を作成 (`make_inverse_operator`)。
  2. `apply_inverse_raw(..., method='eLORETA', lambda2=lambda2)` を適用し、脳内全ソース点（約 31,554 点）における各時刻の電流双極子モーメント密度（$\text{nA/m}$）を推定。
* **期待出力**:
  - ソース空間時系列推定オブジェクト (`stc` / `mne.SourceEstimate`)

---

### Step 4: CerebrA 領域への集約 (Parcellation / MRA 算出)
* **担当ライブラリ**: `MNE-Python` (`mne.extract_label_time_course`), `NumPy`, `Pandas`
* **期待入力**:
  1. Step 3 のソース推定オブジェクト (`stc`)
  2. Step 0-B の CerebrA 領域ラベルリスト (`cerebra_labels`)
  3. Step 0-B の ソース空間定義 (`src`)
* **処理内容**:
  1. 約 3 万点のソース点推定値を、CerebrA の 62 個の皮質領域ごとに空間平均。
  2. 解析対象区間（例: 90秒）にわたって時間平均を算出し、領域別平均活動量（Mean Regional Activation: MRA）を導出。
* **期待出力**:
  - 被験者 $\times$ 実験条件 $\times$ 62領域 の平均活動量データテーブル (`pandas.DataFrame` / CSV)

---

### Step 5: 統計検定 (置換検定) と 3D 脳活動可視化
* **担当ライブラリ**: `SciPy` / `statsmodels` / `MNE-Python`, `Matplotlib`, `Open3D`
* **期待入力**:
  - Step 4 で全被験者・全条件分集約されたデータテーブル
* **処理内容**:
  1. 条件間（例: 安静時 vs 動画視聴時、MATBタスクの負荷難易度間）の活動差について、対応のある置換検定（Paired Permutation Test）を実行。
  2. 有意水準（$p < 0.05$）を満たした領域の差分強度をカラーマップ化し、3D 脳表面メッシュ上にマッピング描画。
* **期待出力**:
  - 統計検定結果（p値、t値、有意領域一覧テーブル）
  - 3D 脳活動マップ画像 / プロット（Figure 6, Figure 7 相当の可視化図面）

---

## 4. データフロー連鎖対応表 (Input/Output Chain Summary)

| ステップ | 担当ライブラリ | 期待入力 (Input) | 期待出力 (Output) | 次の接続先 |
| :--- | :--- | :--- | :--- | :--- |
| **0-A: 幾何再構築** | `FreeSurfer`, `nibabel` | 標準脳 MRI (`.nii`) | 3層BEMメッシュ (`*-bem.surf`) | Step 0-B, 0-C |
| **0-B: アトラス・空間作成** | `cerebra_atlas_python`, `MNE` | BEMメッシュ, `CerebrA.nii` | ソース空間 `src`, 領域ラベル `labels` | Step 0-C, 3, 4 |
| **0-C: 順モデル計算** | `MNE-Python` | BEMメッシュ, `src`, 電極座標 | 順モデル `fwd` (`fwd.fif`) | Step 3 |
| **1: 生EEG前処理** | `MNE-Python`, `pyprep` | 生EEGファイル (`.mff`/`.vhdr`) | クリーンEEG `cleaned_raw` | Step 2, 3 |
| **2: ノイズ共分散・SNR** | `MNE-Python`, `NumPy` | クリーンEEG `cleaned_raw` | ノイズ共分散 `noise_cov`, $\lambda^2$ | Step 3 |
| **3: eLORETA音源推定** | `MNE-Python` | `fwd`, `cleaned_raw`, `noise_cov`, $\lambda^2$ | ソース推定 `stc` | Step 4 |
| **4: 領域集約 (MRA)** | `MNE-Python`, `Pandas` | `stc`, `cerebra_labels`, `src` | 62領域活動量テーブル (`DataFrame`) | Step 5 |
| **5: 統計検定・可視化** | `SciPy`, `Matplotlib`, `Open3D` | 全被験者・条件の領域活動量 | 統計検定結果 (p値) & 3D脳活動図 | 最終成果物 |
