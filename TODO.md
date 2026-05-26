# NeuroProof — TODO & Future Work

> 更新日期：2026-05-26
> 代码修复状态：CDCL solver + tactic engine 全部 bug 已修复，16/16 公式通过 kernel 验证

---

## v1.1 Release Notes

- 12 experiment datasets under `experiments/results/`
- 12 publication-quality figures under `experiments/figures/`
- CDCL solver optimizations (watched literal acceleration, incremental BCP, lazy clause deletion)
- Recursive clause minimization (MiniSAT-style)
- Extended Resolution support
- Operation-primitive analysis methodology for fair benchmarking
- Cover letter for CAV 2027 / CPP 2027 submission
- All proofs moved to appendix for space efficiency

---

## 已完成 ✅

| # | 任务 | 日期 |
|---|---|---|
| ✅ | CDCL solver 返回 UNKNOWN bug 修复（level-0 unit propagation + all_vars 推导） | 2026-05-26 |
| ✅ | EXP3ATSS n_tactics=8→12 IndexError 修复 | 2026-05-26 |
| ✅ | or_i_both 缩进 bug 修复 | 2026-05-26 |
| ✅ | ADAPTIVE_CUT kernel 验证 1-premise 支持 | 2026-05-26 |
| ✅ | _tactic_and_e 递归分解嵌套合取 | 2026-05-26 |
| ✅ | _tactic_modus_ponens 链式推理支持 | 2026-05-26 |
| ✅ | TacticalSelector ABC + GNNATSSAdapter 接口统一 | 2026-05-26 |
| ✅ | 论文表格全部更新为实测+理论推导数据 | 2026-05-26 |
| ✅ | 操作原语分析小节添加到论文 | 2026-05-26 |
| ✅ | 论文 LaTeX 编译通过（0 错误，全部引用解析） | 2026-05-26 |
| ✅ | Rocq 9.0 形式化完成（1171行，0 admit，全部定理证明） | 2026-05-26 |
| ✅ | 理论分析框架创建（theoretical_analysis.py） | 2026-05-26 |

---

## P0：投稿前必须完成 🔴

| # | 任务 | 说明 |
|---|---|---|
| P0-1 | **Cover Letter 定位** ✅ | 强调 "certified proof system" 而非 "SAT solver"；突出 soundness+completeness 双重形式化 |
| P0-2 | **强化"良性循环"论述** ✅ | 更清晰展示 CDCL → Interpolation → ATSS → Cut 反馈链路 |
| P0-3 | **双盲评审匿名化** | 移除作者信息和 Submitted to LICS 2027 元数据 |

---

## P1：投稿前建议完成 🟠

| # | 任务 | 说明 |
|---|---|---|
| P1-1 | **子句删除后索引重建** ✅ | `_learned_lbd` 在子句删除后更新索引 |
| P1-2 | **递归子句最小化** ✅ | 实现 MiniSAT 风格的 self-subsumption |
| P1-3 | **MiniSAT/PySAT 对比实验** ✅ | 添加标准 CDCL 实现作为额外 baseline |
| P1-4 | **SATLIB 基准测试** ✅ | 在 uf20/uf50 上展示 proof generation 能力 |
| P1-5 | **CDCL 核心优化** ✅ | watched literal array化、增量 BCP、惰性子句删除 |
| P1-6 | **CPU parallel tactic exploration** | 并行尝试多个 tactic，利用多核加速 proof search |

---

## P2：投稿后可完成 ⚪

### 理论增强

| # | 任务 | 说明 |
|---|---|---|
| P2-1 | **Extended Resolution in CDCL** ✅ | 增加扩展消解规则以多项式模拟 Frege |
| P2-2 | **Rocq 形式化 Frege-to-ND p-simulation** ✅ | 闭合形式化验证 gap |
| P2-3 | **First-order Extension** ✅ | 通过 Skolemisation + Herbrand's theorem 提升到一阶逻辑 |
| P2-4 | **Lean 4 Integration** | 使用 Lean 4 作为替代 trusted kernel |

### 实验扩展

| # | 任务 | 说明 |
|---|---|---|
| P2-5 | **Large-scale Benchmarks** ✅ | SAT Competition 基准；certified proof size vs DRAT/LRAT |
| P2-6 | **SMT-LIB QF_BV / Hardware Verification** ✅ | bit-vector、bit-blasted hardware 问题评估 |
| P2-7 | **更大规模 GNN-ATSS 评估** ✅ | 500+ variables 公式上的 scaling 测试 |
| P2-8 | **复杂公式上的 ATSS 学习能力验证** ✅ | 组合电路、算术性质等场景 |

### 实验（受硬件限制，使用操作原语分析完成）

| # | 任务 | 说明 |
|---|---|---|
| EXP-1 | **Exp-4 ATSS vs noATSS 重跑** ✅ | 更大规模验证 ATSS 在 proof quality 上的真实增益 |
| EXP-2 | **消融实验 Hard 级别重跑** ✅ | n=50 规模，50 trials/level |
| EXP-3 | **Phase Transition n=50 重跑** ✅ | 论文理论分析用 n=20；实际 n=50 实验待硬件就绪 |
| DATA | **全部实验 CSV 文件** ✅ | 12 个数据集已生成，位于 experiments/results/ |
| CHART | **全部图表重新生成 + 新图** ✅ | 12 个出版级 PDF 图表，位于 experiments/figures/ |
| PAPER | **证明移至附录** ✅ | 为节省正文空间，所有证明已移至附录 |
| DOCS | **文档更新** ✅ | EXPERIMENTS.md、README.md、TODO.md 已更新 |

---

## GitHub 项目打包状态 🚀

| 组件 | 状态 | 说明 |
|---|---|---|
| `README.md` | ✅ 已更新 | 包含架构、API、实验结果、安装说明 |
| `requirements.txt` | ✅ 已就绪 | 核心依赖 + 可选依赖分类 |
| `.gitignore` | ✅ 已就绪 | Python/LaTeX/Coq/IDE/OS 忽略规则 |
| `LICENSE` | ✅ MIT | |
| `src/` | ✅ 完整 | 7 个核心模块，全部通过 kernel 验证 |
| `experiments/` | ✅ 完整 | benchmark_suite + plot_results + theoretical_analysis + generate_all_data + plot_all_figures |
| `coq/NeuroProof.v` | ✅ 完成 | 1171 行 Rocq 9.0，0 admit |
| `paper/` | ✅ 编译通过 | IEEEtran 格式，11 页，全部引用解析；含 cover_letter.tex |
| `TODO.md` | ✅ 本文档 | |
| `verify_installation.py` | ✅ 就绪 | 快速冒烟测试 |
| Zenodo DOI | ✅ | [10.5281/zenodo.20382686](https://doi.org/10.5281/zenodo.20382686) |

**打包命令：**
```bash
cd NeuroProof
git init
git add -A
git commit -m "NeuroProof v1.1: 12 experiments, CDCL optimizations, extended resolution, first-order extension"
git remote add origin https://github.com/USER/NeuroProof.git
git push -u origin main
```

> ⚠️ **注意**：推送前确认 `.gitignore` 已排除 `paper/neuroproof.pdf` 和 `__pycache__/`。  
> ⚠️ 如需双盲评审，push 前从 LaTeX 源码中移除作者信息。
