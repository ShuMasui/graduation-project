# 高密度EEG解析 再現実験 (exp-reproduce)

本ディレクトリは、論文（*Carlos Gomez-Tapia et al., 2025: "Evaluation of EEG pre-processing and source localization in ecological research"*）における高密度EEG前処理・動的正則化eLORETA音源推定・CerebrA領域集約パイプラインを再現するためのプログラム群です。

各ステップは完全な独立モジュールとして実装され、最上位の `main.py` によって線形にオーケストレーション（結合実行）されます。

---

## 1. 計算用PCでの環境構築手順

計算用PCに本リポジトリを展開した後、以下の手順で Python 3.10 環境を構築してください。

```bash
# 1. exp-reproduce ディレクトリへ移動
cd exp-reproduce

# 2. Python 仮想環境の作成と有効化 (pyenv または venv)
# 例: venv の場合
python3.10 -m venv .venv
source .venv/bin/activate

# 3. 依存ライブラリのインストール
pip install --upgrade pip
pip install -r requirements.txt

# 4. 単体テストの実行（全36テストがパスすることを確認）
python -m unittest discover -s modules -p "test_*.py"
```

---

## 2. ダウンロード対象データ一覧 & 配置先ディレクトリ

再現実験を実行するには、外部から **「解剖テンプレート・アトラスデータ」** と **「実験EEGデータ」** をダウンロードして所定のパスに配置する必要があります。

```text
exp-reproduce/
├── subjects/                           # 【配置先 A】FreeSurfer / テンプレート脳ディレクトリ
│   └── icbm152/                        # MNI-ICBM152 2009c 幾何・BEM・ソース空間データ
│       ├── bem/                        # BEM サーフェス (*-bem.fif, *-bem-sol.fif)
│       └── surf/                       # 皮質サーフェス (lh.white, rh.white 等)
│
├── atlas/                              # 【配置先 B】CerebrA アトラスデータ
│   ├── CerebrA.nii                     # CerebrA ラベル画像 (NIfTI 形式)
│   └── CerebrA_LabelDetails.csv        # CerebrA 領域名対応表 CSV
│
└── data/                               # 【配置先 C】実験 EEG 生データ
    ├── sub-01_rest_raw.fif             # 被験者01 安静時 (または .mff / .vhdr)
    ├── sub-01_video1_raw.fif           # 被験者01 動画視聴1
    ├── sub-02_rest_raw.fif
    └── sub-02_video1_raw.fif
```

---

## 3. 各データの詳細入手先 & ダウンロード手順

### 3.1 解剖テンプレート (Phase 1 共通モデル)
- **対象データ**: MNI-ICBM 2009c Nonlinear Symmetric テンプレート
- **配置先**: `exp-reproduce/subjects/icbm152/`
- **入手先 & 推奨手順**:
  - FreeSurfer の `recon-all` には半日以上の計算時間を要するため、CerebrA Python リポジトリ等で公開されている事前構築済み `icbm152` フォルダをそのまま配置することを推奨します。
  - **ダウンロード元**: [MNI ICBM 152 ページ](https://nist.mni.mcgill.ca/icbm-152-nonlinear-atlases-2009/) または [kdotdot/cerebra_atlas_python](https://github.com/kdotdot/cerebra_atlas_python)

---

### 3.2 CerebrA Atlas (Phase 1 共通モデル)
- **対象データ**: `mni_icbm152_CerebrA_tal_nlin_sym_09c.nii` および `CerebrA_LabelDetails.csv`
- **配置先**: `exp-reproduce/atlas/`
- **入手先**:
  - **ダウンロード元**: [CerebrA GIN Repository (anamanera/CerebrA)](https://gin.g-node.org/anamanera/CerebrA)
  - ※ リポジトリ内 `exp-reproduce/atlas/` にすでに CSV および NIfTI ファイルが配置されています。

---

### 3.3 実験用高密度 EEG データ (Phase 2 解析用)

以下のいずれか（または両方）をダウンロードし、`exp-reproduce/data/` 配下に配置します。

#### A. HBN (Healthy Brain Network) データセット *(推奨・論文主実験)*
- **仕様**: 128ch EGI HydroCel GSN 電極 (500 Hz)
- **実験タスク**:
  - 安静時: `RestingState` (90秒)
  - 動画視聴: `Video1` (*Despicable Me* 等), `Video2` (*The Present*), `Video3` (*Fun with Fractals*)
- **ダウンロード方法 (AWS S3 CLI)**:
  ```bash
  # AWS CLI を用いたダウンロード例 (公開 S3 バケット: 認証不要)
  aws s3 sync --no-sign-request s3://fcp-indi/data/Projects/HBN/EEG/ ./data/HBN/
  ```
- **Web ポータル**: [Healthy Brain Network Data Portal](https://data.healthybrainnetwork.org/main.php)

#### B. COG-BCI データセット
- **仕様**: 64ch ActiCap 電極 (500 Hz)
- **実験タスク**:
  - 安静時（開眼 / 閉眼: 各60秒）
  - MATB-II タスク（Easy, Medium, Hard の認知負荷タスク）
- **入手先**: [Scientific Data (Hinss et al., 2023)](https://doi.org/10.1038/s41597-022-01898-y) / Zenodo

---

## 4. パイプラインの実行手順 (計算用PC)

データ配置完了後、最上位オーケストレータを実行します。

```bash
# パイプラインの実行
python main.py
```

### 実行の流れ
1. **[Phase 1] 共通モデル構築**:
   - Step 0-A (3層BEM), Step 0-B (3万点ソース空間 & CerebrA 62領域), Step 0-C (128ch 順モデル) を事前計算（またはキャッシュから高速ロード）。
2. **[Phase 2] 被験者データ解析ループ**:
   - 各被験者・各条件に対して、Step 1 (前処理), Step 2 (動的正則化 $\lambda^2=1/\text{SNR}^2$ 算出), Step 3 (eLORETA 音源推定), Step 4 (CerebrA 62領域平均活動量 MRA 抽出) を実行。
   - `results/all_subjects_mra.csv` に全活動量データを集約。
3. **[Phase 3] 統計検定 & 可視化**:
   - Step 5 (10,000回ベクトル化置換検定) を実行し、`results/` 配下に統計結果 CSV および 3D/2D グラフ画像を保存。

---

## 5. 出力ファイル一覧 (`results/`)

実行完了後、`results/` ディレクトリに以下の成果物が出力されます。

| 出力ファイル | 内容 |
| :--- | :--- |
| `all_subjects_mra.csv` | 全被験者・全条件・62皮質領域の平均活動量（$\text{nA/m}$）テーブル |
| `permutation_test_results.csv` | 条件間の対応のある置換検定統計結果（差分平均、p値、有意判定） |
| `condition_comparison_boxplot.png` | 条件別の領域活動量ボックスプロット図 (論文 Figure 4 相当) |
| `mra_difference_barplot.png` | 領域別活動差分値の有意水準付きバープロット図 |
| `p_value_distribution.png` | 置換分布と観測統計量のヒストグラム図 (論文 Figure 5 相当) |
