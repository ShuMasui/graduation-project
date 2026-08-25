# 高密度EEG信号処理と動的正則化eLORETA音源推定パイプラインの数学的定式化

本ディレクトリは、高専フォーマット（LaTeX / `jsarticle`）による詳細技術報告書およびそのビルド成果物を格納しています。

- **LaTeX ソース原稿**: [`mathematical_formulation.tex`](file:///Users/shumasui/Documents/school/graduation-project/docs/exp-reproduce/report/mathematical_formulation.tex)
- **BibTeX 参考文献**: [`mathematical_formulation.bib`](file:///Users/shumasui/Documents/school/graduation-project/docs/exp-reproduce/report/mathematical_formulation.bib)
- **ビルド済み PDF 報告書**: [`latex-output/mathematical_formulation.pdf`](file:///Users/shumasui/Documents/school/graduation-project/docs/exp-reproduce/report/latex-output/mathematical_formulation.pdf)

---

## 数学的定式化の全体概要（ステップ別）

```mermaid
flowchart TD
    subgraph Step 0: 順問題 & 幾何モデリング
        M1["準静的ポアソン方程式:<br>∇・(σ∇Φ) = ∇・J_p"] --> M2["3層BEM境界積分方程式<br>(Brain, Skull, Scalp)"]
        M2 --> M3["Lead Field 行列 L ∈ ℝ^(N_ch × 3N_src):<br>v(t) = L j(t) + ε(t)"]
    end

    subgraph Step 1: 生EEG前処理
        P1["リサンプリング: 500Hz -> 125Hz"] --> P2["FIR ゼロ位相フィルタ: 1.0 - 50.0 Hz"]
        P2 --> P3["PREP 球面スプライン異常電極補間 & 平均再参照"]
        P3 --> P4["FastICA (ネゲントロピー最大化) による眼球運動・筋電除去"]
    end

    subgraph Step 2: ノイズ共分散 & 動的SNR 正則化
        C1["経験的共分散行列: C = 1/(T-1) Σ (v - v̄)(v - v̄)^T"]
        C2["瞬時パワー: p(t) = 1/N_ch ||v(t)||_2^2"]
        C2 --> C3["平均パワー P = E[p(t)], 分散 σ^2 = Var[p(t)]"]
        C3 --> C4["動的正則化パラメータ:<br>λ^2 = 1/SNR^2 = σ^2 / P"]
    end

    subgraph Step 3: eLORETA 逆問題求解
        I1["重み付き最小二乗最適化:<br>min ||C^(-1/2)(v - L j)||_2^2 + λ^2 j^T W j"]
        I2["局在化誤差ゼロ重み更新:<br>W_k = [L_k^T (L W^(-1) L^T + λ^2 C)^(-1) L_k]^(1/2)"]
        I1 --> I2
        I2 --> I3["線形逆作用素:<br>G = W^(-1) L^T (L W^(-1) L^T + λ^2 C)^(-1)"]
        I3 --> I4["音源電流密度推定: ĵ(t) = G v(t)"]
    end

    subgraph Step 4: CerebrA 領域集約 (MRA)
        A1["空間平均: A_r(t) = 1/|V_r| Σ ||ĵ_j(t)||_2 (r=1..62)"]
        A1 --> A2["時間平均 (MRA): MRA_r = 1/T ∫ A_r(t) dt"]
    end

    subgraph Step 5: 対応のある置換検定
        S1["被験者ペア差分: d_(s,r) = X_(s,r)^B - X_(s,r)^A"]
        S2["符号反転ブロードキャスト (10,000回):<br>M_perm = 1/S Σ (S_(k,s,1) ・ D_(s,r))"]
        S1 --> S2
        S2 --> S3["ノンパラメトリック 2側 p値:<br>p_r = 1/K Σ I(|(M_perm)_(k,r)| ≥ |d̄_r|)"]
    end

    M3 --> I1
    P4 --> C1
    P4 --> C2
    C4 --> I1
    I4 --> A1
    A2 --> S1
```

---

## 各章の構成と数式詳細

### 第1章 まえがき
- 生態学的（Ecological）研究における高密度脳波計測の意義
- 脳波逆問題の不良設定性（$N_{ch} \ll 3N_{src}$）

### 第2章 頭部順問題と3層境界要素法 (BEM) の数理
- 電磁場の準静的マクスウェル方程式:
  $$\nabla \cdot (\sigma(\mathbf{r}) \nabla \Phi(\mathbf{r})) = \nabla \cdot \mathbf{J}_p(\mathbf{r})$$
- 3層（脳・頭蓋骨・皮膚）境界条件と境界積分離散化
- リードフィールド行列表現:
  $$\mathbf{v}(t) = \mathbf{L} \mathbf{j}(t) + \boldsymbol{\epsilon}(t) \quad (\mathbf{L} \in \mathbb{R}^{128 \times 94662})$$

### 第3章 皮質ソース空間幾何とアトラス写像の数理
- 正20面体細分化（`oct-6`）による約31,554点の皮質表面離散化
- CerebrA アトラスによる大脳皮質 62 領域（左右各31領域）のボクセル写像 $\mathcal{V}_r$

### 第4章 生EEG信号前処理の数理モデル
- ポリフェーズ・リサンプリング（500 Hz $\rightarrow$ 125 Hz）
- 線形位相 FIR バンドパスフィルタ（1.0〜50.0 Hz）
- PREP 球面スプライン補間と平均再参照行列 $\mathbf{R} = \mathbf{I} - \frac{1}{N_{ch}} \mathbf{1}\mathbf{1}^T$
- FastICA（ネゲントロピー最大化固定小数点アルゴリズム）によるノイズ成分除去

### 第5章 ノイズ共分散推定と動的正則化パラメータ $\lambda^2$ の適応導出
- 瞬時平均信号パワー:
  $$p(t) = \frac{1}{N_{ch}} \|\mathbf{v}(t)\|_2^2$$
- 信号平均パワー $P = \mathbb{E}[p(t)]$、瞬時パワーの分散 $\sigma^2 = \operatorname{Var}[p(t)]$
- 動的正則化パラメータの理論導出:
  $$\lambda^2 = \frac{1}{\text{SNR}^2} = \left(\frac{P}{\sigma^2}\right)^{-1} = \frac{\sigma^2}{P}$$

### 第6章 eLORETA 音源推定の厳密数理
- 重み付き最小二乗最適化:
  $$\min_{\mathbf{j}(t)} \left\{ \|\mathbf{C}^{-1/2} (\mathbf{v}(t) - \mathbf{L} \mathbf{j}(t))\|_2^2 + \lambda^2 \mathbf{j}(t)^T \mathbf{W} \mathbf{j}(t) \right\}$$
- 単一双極子に対する局在化誤差ゼロ（Exact Zero Error Localization）を満たす反復重み更新式:
  $$\mathbf{W}_k = \left[ \mathbf{L}_k^T (\mathbf{L} \mathbf{W}^{-1} \mathbf{L}^T + \lambda^2 \mathbf{C})^{-1} \mathbf{L}_k \right]^{1/2}$$
- 解析的線形逆作用素 $\mathbf{G}$:
  $$\hat{\mathbf{j}}(t) = \mathbf{G} \mathbf{v}(t), \quad \mathbf{G} = \mathbf{W}^{-1} \mathbf{L}^T (\mathbf{L} \mathbf{W}^{-1} \mathbf{L}^T + \lambda^2 \mathbf{C})^{-1}$$

### 第7章 CerebrA 62領域平均活動量 (MRA) の空間・時間集約
- 空間平均 $A_r(t) = \frac{1}{|\mathcal{V}_r|} \sum_{j \in \mathcal{V}_r} \|\hat{\mathbf{j}}_j(t)\|_2$
- 時間平均 $\text{MRA}_r = \frac{1}{T} \int_0^T A_r(t) \, dt$

### 第8章 対応のあるノンパラメトリック置換検定の完全ベクトル化数理
- ペア差分 $d_{s, r} = X_{s, r}^B - X_{s, r}^A$、観測平均差 $\bar{d}_r = \frac{1}{S} \sum_{s=1}^S d_{s, r}$
- 符号反転テンソル $\mathbf{S} \in \{-1, +1\}^{10000 \times S \times 1}$ によるブロードキャスト行列積:
  $$\mathbf{M}_{perm} = \frac{1}{S} \sum_{s=1}^S (\mathbf{S}_{k, s, 1} \cdot \mathbf{D}_{s, r})$$
- 2側検定ノンパラメトリック $p$ 値:
  $$p_r = \frac{1}{K} \sum_{k=1}^K \mathbb{I}\left(|(\mathbf{M}_{perm})_{k, r}| \ge |\bar{d}_r|\right)$$

### 第9章 むすび & 妥当性の総括
- 数理モデルの正当性と、NumPy/Pandas による完全ベクトル化実装との対応関係の証明。
