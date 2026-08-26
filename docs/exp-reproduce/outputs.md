# Phase 1: 再現実験 成果・ノウハウ記録 (outputs.md)

本ドキュメントは、[CLAUDE.md](file:///Users/shumasui/Documents/school/graduate-project/CLAUDE.md) に基づき、Phase 1（高密度EEG処理再現実験）の実装成果、検証結果、および開発で得られた知見・ノウハウを記録する一次情報源です。

---

## 1. 実装成果一覧

`exp-reproduce/` 配下に、参照論文（*Gomez-Tapia et al., 2025*）の処理パイプラインを再現する独立モジュール群および最上位オーケストレータを完全実装しました。

| モジュール | パス | 責務 | テスト件数・結果 |
| :--- | :--- | :--- | :--- |
| **Step 0-A** | [`modules/step0a_geometry_bem`](file:///Users/shumasui/Documents/school/graduate-project/exp-reproduce/modules/step0a_geometry_bem) | 3層 BEM 電気伝導モデル構築 | 5 tests / PASS |
| **Step 0-B** | [`modules/step0b_atlas_source`](file:///Users/shumasui/Documents/school/graduate-project/exp-reproduce/modules/step0b_atlas_source) | CerebrA 変換 & 31,554点ソース空間 | 5 tests / PASS |
| **Step 0-C** | [`modules/step0c_forward_model`](file:///Users/shumasui/Documents/school/graduate-project/exp-reproduce/modules/step0c_forward_model) | 128ch 電極共登録 & 順モデル計算 | 5 tests / PASS |
| **Step 1** | [`modules/step1_preprocessing`](file:///Users/shumasui/Documents/school/graduate-project/exp-reproduce/modules/step1_preprocessing) | リサンプル(125Hz)、フィルタ、PREP、ICA | 4 tests / PASS |
| **Step 2** | [`modules/step2_noise_covariance`](file:///Users/shumasui/Documents/school/graduate-project/exp-reproduce/modules/step2_noise_covariance) | ノイズ共分散・動的 $\lambda^2=1/\text{SNR}^2$ 算出 | 2 tests / PASS |
| **Step 3** | [`modules/step3_source_localization`](file:///Users/shumasui/Documents/school/graduate-project/exp-reproduce/modules/step3_source_localization) | eLORETA 音源電流密度推定 | 4 tests / PASS |
| **Step 4** | [`modules/step4_parcellation`](file:///Users/shumasui/Documents/school/graduate-project/exp-reproduce/modules/step4_parcellation) | CerebrA 62領域平均活動量 (MRA) 集約 | 5 tests / PASS |
| **Step 5** | [`modules/step5_stats_visualization`](file:///Users/shumasui/Documents/school/graduate-project/exp-reproduce/modules/step5_stats_visualization) | ベクトル化置換検定 (10,000回) & 8方向皮質脳活動マップ (2×4 300DPI) | 10 tests / PASS |
| **Orchestrator** | [`main.py`](file:///Users/shumasui/Documents/school/graduate-project/exp-reproduce/main.py) | パイプライン結合実行・耐障害性ループ | 結合動作確認済 |

**単体テスト総合結果**: **40 / 40 テスト合格 (100% PASS)**

---

## 2. 開発で得られた知見・ノウハウ (Know-how & Insights)

1. **順方向単方向 DTO 契約の有効性**:
   - 各ステップが前段の `output.py` のみに型依存する構造にしたことで、全モジュールを完全に独立して並行実装・単体テストすることが可能となった。
2. **NumPy による置換検定の超高速化**:
   - 通常 10,000 回の置換ループ（`for` 文）を回すと数秒〜数十秒かかる検定を、符号反転行列 $S \in \{-1, +1\}^{10000 \times N_{sub} \times 1}$ のブロードキャスト積による完全ベクトル化演算とすることで、ミリ秒オーダー（0.05秒以下）で瞬時に完了できる。
3. **MRA 時間集約のベクトル化**:
   - `mne.extract_label_time_course`（形状: $62 \times T$）から `np.mean(label_tc, axis=1)` で一括平均することで、ループ処理を排除し数学的説明性と計算効率を両立した。
4. **ヘッドレス 8方向脳活動マップ（2×4 統合図面）の高速描画**:
   - FreeSurfer の膨張皮質（`lh.inflated`, `rh.inflated`）および `src[0]['use_tris']`（8,192ポリゴン/半球）を活用し、Matplotlib 3D（`Poly3DCollection`）でヘッドレス描画。
   - 8標準視点（Anterior, Posterior, Superior, Inferior, Left Lateral, Right Lateral, Left Medial, Right Medial）に対して各半球の分離描画（Medial ビュー時は片側半球のみを描画）と視点ごとの自動バウンディングボックス調整を行い、知覚的一様な `viridis` 共通カラースケール（vmin, vmax）の 300 DPI 統合図面を高速出力。
5. **共通モデルのキャッシュ機構**:
   - テンプレート脳の BEM 解（`bem-sol.fif`）や順モデル（`fwd.fif`）は全被験者で共通のため、初回計算後にファイル保存し、次回以降はロードのみを行うことで解析全体の所要時間を大幅に削減できる。

---

## 3. 実データ実行に向けた準備チェックリスト

- [x] 解剖テンプレート（事前計算済み FreeSurfer `subjects/icbm152/` フォルダ）の配置
- [x] CerebrA NIfTI 画像（`CerebrA.nii`）の配置
- [ ] HBN または COG-BCI の生 EEG データ（`.fif` / `.mff` 等）の配置
- [ ] `exp-reproduce/main.py` の被験者 ID・条件リストを設定して本番実行

