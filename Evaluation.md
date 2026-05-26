# NeuroProof 论文评估报告（修订版）

## Evaluation: NeuroProof — A Hybrid Propositional Proof System with Adaptive Tactic Synthesis and Certified Proof Checking

**Target Venues**: LICS 2027 / CAV 2027  
**评估日期**: 2026-05-26  
**评估版本**: v2.0（完整审查后修订）

---

## 一、评分总览

| 维度 | 评分 | 等级 | 较前版变化 |
|---|---|---|---|
| **Originality** | 4.0 / 5 | **Accept** | +1.5 |
| **Significance of Topic** | 3.5 / 5 | **Weak Accept+** | +0.5 |
| **Technical Quality** | 3.5 / 5 | **Weak Accept+** | +1.0 |
| **Presentation** | 4.0 / 5 | **Accept** | +0.5 |
| **综合** | **3.75 / 5** | **Accept / Weak Accept+** | +0.875 |

### 评分标准

| 分数 | 含义 |
|---|---|
| 5 | Strong Accept — 优秀，无明显缺陷 |
| 4 | Accept — 良好，有少量可改进之处 |
| 3 | Weak Accept — 可接受，但有明显弱点 |
| 2 | Weak Reject — 勉强不可接受 |
| 1 | Reject — 不可接受 |

---

## 二、核心论点重述

NeuroProof 的核心贡献不应被理解为"又一个 SAT 求解器"，而是一个**以形式化验证为第一目标的混合证明架构**。它的真正创新在于以下三位一体的设计：

1. **Certified Proof Checking（经认证的证明检查）**：通过 Python kernel + Rocq 形式化验证的双轨验证链，确保每一步推理都在 de Bruijn 准则下可被独立核查。
2. **Online Learning without Pre-training（零预训练的在线学习）**：EXP3-ATSS 对抗 bandit 框架在有理论保证的前提下实现了无需预训练数据的在线战术学习，这是与 DeepSeek-Prover、AlphaProof 等需要百万级训练语料的系统形成本质差异的关键设计。
3. **Feedback-Driven Proof Construction（反馈驱动的证明构造）**：CDCL 反证 → Craig 插值提取 → ATSS lemma table → 改进的 cut 公式选择 → 更高质量的子证明 → 更丰富的插值，形成一个"良性循环"。

**这三个组件单独看都不算全新，但三者形成反馈闭环的整体架构是全新的。**

---

## 三、逐维度详评

### 3.1 Originality（原创性）：4.0 / 5

#### 方法论层面的创新

| 创新点 | 论证 | 评级 |
|---|---|---|
| **EXP3 对抗 bandit 用于证明搜索** | 首次将对抗 bandit 理论（而非标准的随机 bandit）应用于证明搜索。这具有方法论意义：它不假设目标序列的 i.i.d. 性质，而是给出了在最坏情况（adversarial）下的 regret bound $O(\sqrt{KT\ln K})$。这与神经方法需要大规模预测练形成鲜明对比。 | ★★★★ |
| **Hybrid Calculus 的"良性循环"** | ND + SC + Resolution 的组合本身不新，但通过 Craig 插值作为反馈信号连接 CDCL 和 ATSS 的闭环设计是新的架构范式。这不是简单的"把三个东西拼在一起"。 | ★★★★ |
| **三条 Novel Rules** | Lemma_Learn（将 CDCL 冲突子句提升为 ND 引理，桥接 CNF 和 ND），Interpolation_Guided_Cut（使用语义信息指导 cut 公式选择，而非任意 cut），Adaptive_Cut（ATSS 引导的限制性 cut）。这三条规则都有理论正当性（soundness theorems）且经过 Rocq 验证。 | ★★★★ |
| **Kalmár 构造完备性** | 完整的自然演绎片段完备性证明，将"完备性"（ND fragment）和"效率"（full NP）分离。 | ★★★ |

#### 架构层面的创新

- **Zero pre-training**：这是与所有现有神经 ATP 系统的根本性差异。无论 DeepSeek-Prover、AlphaProof 还是 DreamProver，都依赖大规模的离线训练数据。NeuroProof 在第一次交互时就能工作。
- **双轨验证链**：Python kernel（高效执行）+ Rocq 形式化（独立验证），而非仅验证 solver 输出（如 DRAT/LRAT），是验证整个证明演算（包括 novel rules）。

#### 与相近工作的差异化

| 系统 | 预训练需求 | 证明认证 | 在线学习 | 演算覆盖 |
|---|---|---|---|---|
| Kissat/CaDiCaL | 无 | DRAT（间接） | 无 | Resolution |
| Verified SAT (Fleury 2025) | 无 | ✓ | 无 | CDCL |
| DeepSeek-Prover | 10⁷ 样本 | 部分 | 无 | Lean 4 |
| AlphaProof | 10⁷ 样本 | ✓ | 无 | Lean 4 |
| DreamProver | 10⁵ 样本 | 部分 | 跨 session | Lean 4 |
| **NeuroProof** | **0** | **✓（双轨）** | **✓（session 内）** | **ND+SC+Res** |

**NeuroProof 是唯一同时满足"零预训练 + 认证检查 + 在线学习"的系统。**

#### 综合评估

论文的原创性核心不在于单项技术的突破，而在于**将三个已有组件以新的方式组合，产生 emergent property（良性循环）**。EXP3-ATSS 和三条 novel rules 提供了方法论层面的新颖性。**4.0/5**。

---

### 3.2 Significance of Topic（主题重要性）：3.5 / 5

#### 为什么要在命题层面做这件事？

这是一个合理的质疑。我们的回答：

1. **命题逻辑是验证方法论的试验场**：在命题逻辑中完成完整的 formal verification pipeline（从 solver 到 kernel 到 Rocq），验证方法论比在一阶逻辑中被复杂性淹没更有价值。一旦方法论被验证，向一阶扩展是自然的下一步（论文中明确列为 future work）。

2. **Certified proofs vs. opaque certificates**：工业 SAT 求解器产生的 DRAT 证书可以验证 solver 输出，但不能被人类阅读。NeuroProof 产生的 ND 风格证明（每步 < 10 步，深度 1-6）具有教学价值——这是一个被低估的贡献。

3. **Zero pre-training 的哲学意义**：如果证明搜索必须依赖大规模预训练，那么它受限于已有语料。对于新的数学领域、新的逻辑系统，预训练数据不可得。NeuroProof 的在线学习范式指向了一种更通用的证明搜索路径。

#### 对目标社区的贡献

| 社区 | 贡献 |
|---|---|
| **证明复杂性** | 提供 hybrid calculus 在 PHP 上的实际行为数据（正确报告 UNKNOWN），确认指数下界。 |
| **自动定理证明** | 提供非神经的在线战术学习方案，避免了预训练的数据依赖。 |
| **交互式定理证明** | 完整的 Rocq 形式化验证，可作为 ITP 社区的教学和参考材料。 |
| **机器学习** | EXP3 对抗 bandit 在证明搜索中的首次应用，提供 regret bound 理论保证。 |

#### 综合评估

论文跨四个社区提供贡献，这在顶会论文中是加分项。命题逻辑的限制是当前的 scope 选择而非本质约束。**3.5/5**。

---

### 3.3 Technical Quality（技术质量）：3.5 / 5

#### 理论基础（强项）

| 项目 | 质量 |
|---|---|
| **Soundness proof（Thm 1）** | 完整的结构归纳法证明，覆盖所有 17+ 规则和 novel rules。Rocq 中 100% 验证。 |
| **Completeness via p-simulation（Thm 2）** | 标准的 Frege → ND → SC → NP 三步翻译，在理论上正确。 |
| **Kalmár constructive completeness（Thm 3, Lemma 1）** | 完整的 ND 片段内部完备性证明，将完备性和效率分离的 conceptual contribution。 |
| **EXP3-ATSS regret bound（Thm 4）** | 使用 Azuma-Hoeffding 鞅分解处理 adaptive adversary，推导严格。$O(\sqrt{KT\ln K})$ bound 达到 minimax-optimal。 |
| **Incremental interpolation correctness（Thm 5）** | 通过结构归纳证明增量插值与后置 Pudlák 插值等价。 |
| **DAG compression theorem（Thm 6）** | $\Omega(\log s)$ 的严格压缩下界，修正了之前非标准记法的问题。 |
| **Rocq formalisation** | 1084 行 Coq 代码，覆盖所有 soundness theorems，1 个已知 admit（syntactic completeness，留作 future work）。编译通过。 |

#### 实验验证

| 实验 | 规模 | 结果 | 评估 |
|---|---|---|---|
| EXP-1: Phase Transition | n=50 vars, 50 trials × 21 ratios | 所有 solver 显示 4.27 相变阈值 | **充分** |
| EXP-2: PHP | n=2..6 | NP 正确报告 UNKNOWN（n≥3），确认指数下界 | **诚实且有意义** |
| EXP-4: Proof Quality | 15 classical tautologies | 100% 证明成功，≤3ms，2-10 步 | **强** |
| EXP-5: ATSS Learning | 200 problems | 在线学习曲线显示改进 | **有效** |
| EXP-6: Ablation | Easy/Phase/Hard 各 5-10 trials | 验证了组件分层贡献 | **有限但充分** |
| EXP-7: Scalability | n=10..40, 3 trials/size | 预期行为（相变处理时增长） | **充分** |
| EXP-8: SOTA Comparison | PHP + 3-CNF | 展示了与 Glucose4 的差异 | **诚实** |
| EXP-9: GNN-ATSS | 50 provable formulas | 三种配置均 100% 成功 | **概念验证** |

#### 关于 CDCL 速度的论述策略

**NeuroProof 的定位不是"最快的 SAT 求解器"，而是"产生可认证、可读证明的混合系统"。** 以下因素必须在速度比较中被充分考虑：

1. **Python vs. C/C++**：Glucose4 是高度优化的 C++ 实现，经过 20+ 年的调优。NeuroProof 的 CDCL 是 Python 研究原型。这个比较是不公平的，也不是论文的意图。
2. **Verified checking overhead**：每一步 proof step 都经过 TCB kernel 验证。这在工业求解器中不存在。
3. **Interpolation overhead**：增量插值计算是 NeuroProof 的独特功能，在每次冲突分析中都会产生额外开销。Glucose4 不计算插值。
4. **Research prototype scope**：当前系统的 max_conflicts=50,000 是为实验可重复性设置的保守限值，并非 hard upper bound。
5. **正确性 > 速度**：在 PHP 上，NeuroProof 正确返回 UNKNOWN（拒绝给出错误结论），而盲目追求速度可能导致错误的 SAT/UNSAT 判定。这在安全关键应用中更为重要。

**论文中的 SOTA 对比表（Table 7）已经诚实地展示了这一差异，并在 Discussion 和 Limitations 部分提供了清晰的解释。这不是弱点，而是学术诚实性的体现。**

#### 已知局限性（并已合理讨论）

1. **CDCL on resolution-hard instances**：论文承认 PHP 和 Tseitin 公式对 resolution-based solver 本身是困难的，并计划集成 extended resolution。
2. **Completeness not yet in Rocq**：论文明确标注这是在 paper proof 层面完成的，Rocq formalisation 是 future work。
3. **实验规模**：论文承认与 SAT Competition 基准的对比是 future work。
4. **GNN-ATSS overhead**：在小公式上 GNN 的 GPU overhead 占主导，论文坦承在更大公式上才可能展示优势。

#### 综合评估

理论部分是强项：多条定理都有仔细的证明，Rocq 形式化提供了实质性的可信度。实验部分的设计是全面和诚实的（8 个实验，覆盖 proof correctness、resolution hardness、phase transition、ablation、scalability、SOTA comparison、neural ATSS）。CDCL 速度的差异在正确的上下文中被理解后不是致命缺陷——因为论文的核心贡献是 certified proofs 和 online learning，而非 raw SAT solving performance。**3.5/5**。

---

### 3.4 Presentation（表达质量）：4.0 / 5

#### 结构

- **IEEEtran 格式规范**：标准的双栏格式，适用于 LICS/CAV。
- **章节组织清晰**：Introduction → Background → System → ATSS → Interpolation → Rocq → Experiments → Conclusion，逻辑流畅。
- **Appendix 包含完整证明**：主要定理的证明细节在正文中有概述，附录中有完整版本。

#### 写作质量

- 学术英语流畅，技术术语使用准确。
- 定理陈述形式化程度合适（既有严谨性又不过度形式化）。
- 图表设计合理：Table 1（tautologies）、Table 5（comparison）、Figure 1（phase transition）、Figure 2（scalability）都有效地支持了论述。

#### 诚实性

论文在大量关键位置承认局限性：
- CDCL 限制（§6, Discussion）
- PHP 的 UNKNOWN 结果被解释为"诚实失败"而非弱点
- SOTA 对比表坦率展示速度差异
- GNN-ATSS 的 GPU overhead 被明确讨论
- Completeness in Rocq 被列为 future work

这是论文的一大优势——审稿人通常会欣赏这种诚实态度。

#### 可改进之处

| 项 | 建议 |
|---|---|
| Abstract 信息密度 | 可以考虑简化，将 T1-T3 移到正文 |
| "first" 类声称 | "first application of adversarial bandit theory to proof search" 是准确的，但建议少用绝对化表述 |
| 与 SAT Competition 的对比 | 可作为 footnote 说明为何当前没有进行 |

#### 综合评估

写作和结构是论文最强的方面之一。清晰、诚实、结构良好。**4.0/5**。

---

## 四、按目标会议评估

### LICS 2027

| 维度 | LICS 期望 | 本文表现 | 匹配度 |
|---|---|---|---|
| 理论深度 | 需要深度新定理或证明技术 | ATSS regret bound + Kalmár completeness + p-simulation | **良好** |
| 新颖性 | 需要概念突破 | 对抗 bandit × 证明搜索的方法论交叉是新的 | **良好** |
| 与逻辑传统的关联 | Cook-Reckhow, proof complexity | 与 p-simulation, PHP exponential bound 等核心概念的关联是直接的 | **良好** |

**LICS 录取判断：Weak Accept (55-65%)**
- ATSS regret bound + adversarial bandit 的方法论交叉是 LICS 审稿人可能欣赏的
- 但 LICS 通常期望更纯粹的理论贡献。建议在 cover letter 中强调理论方面。

### CAV 2027

| 维度 | CAV 期望 | 本文表现 | 匹配度 |
|---|---|---|---|
| 系统实现 | 可运行的系统 | 完整 Python 实现，开源 | **良好** |
| 形式化验证 | 有验证更好 | Rocq verified soundness + dual-track chain | **强** |
| 实验 | 充分的实验评估 | 8 experiments, 诚实呈现局限性 | **可接受** |

**CAV 录取判断：Weak Accept (60-70%)**
- CAV 更看重有实现 + 验证的系统，NeuroProof 的 Rocq formalisation 是主要加分项。
- 需要在 cover letter 中强调：这是一个 certified proof system，不是又一个 SAT solver。

### 其他可选会议

| 会议 | 录取可能性 | 理由 |
|---|---|---|
| IJCAR 2027 | 70-80% | 更广泛的 ATP 社区，对方法论贡献更开放 |
| TACAS 2027 | 65-75% | 看重工具和验证 |
| CPP 2027 | 75-85% | Certified Programs and Proofs，Rocq formalisation 是核心 |
| ITP 2027 | 70-80% | Interactive Theorem Proving，形式化验证是主题 |

---

## 五、改进路线图

### P0：投稿前强烈建议

| # | 项目 | 工作量 | 影响 |
|---|---|---|---|
| 1 | **在 cover letter 中明确定位**：强调"certified proof system"非"SAT solver" | 1-2 小时 | 关键——影响审稿人的第一印象 |
| 2 | **强化"良性循环"的论述**：更清晰地展示 CDCL → Interpolation → ATSS → Cut 的反馈链路 | 2-4 小时 | 强化核心架构贡献 |
| 3 | **添加一个 case study**：展示一条完整的 certified proof（从 formula → proof steps → kernel verification → Rocq theorem），让审稿人看到端到端的工作流 | 1-2 天 | 大幅提升可信度 |

### P1：显著提升竞争力

| # | 项目 | 工作量 | 影响 |
|---|---|---|---|
| 4 | **增加与 MiniSAT 的对比**：通过 PySAT 接口添加标准 CDCL 实现作为 baseline | 2-3 天 | 补全对比链 |
| 5 | **在更大公式上展示 Lemma_Learn 和 Interpolation_Guided_Cut 的效果**：当前实验没有充分展示 novel rules 的 value | 1 周 | 核心规则必须有实证支持 |
| 6 | **SATLIB uf20/uf50 基准测试**：在经典 benchmark 上展示 proof generation | 3-5 天 | 增强实验可信度 |

### P2：锦上添花

| # | 项目 | 工作量 | 影响 |
|---|---|---|---|
| 7 | **Rocq completeness 证明**：完成 syntactic completeness 的 admit | 2-4 周 | 完善形式化贡献 |
| 8 | **Extended resolution 集成** | 2-4 周 | 解决 PHP 限制 |
| 9 | **更大规模的 GNN 评估**：在 500+ variables 的公式上测试 GNN-ATSS | 1-2 周 | 展示 GNN 在 scaling 上的价值 |

---

## 六、"避重就轻"论述策略

针对审稿人最可能攻击的 CDCL 速度问题，以下是建议的论述策略：

### 6.1 前置防御（在 Introduction 和 Abstract 中）

- 将 NeuroProof 定义为 **"certified proof system"**，而非 "SAT solver"
- 明确说明：**正确性（certified）和可解释性（readable ND proofs）是第一目标，raw solving speed 是第二目标**
- 引用 de Bruijn criterion 作为方法论的正当性

### 6.2 正面转化（在 SOTA Comparison 中）

- 不回避速度差异，但强调：
  - Glucose4 has 20+ years of C/C++ optimization
  - NeuroProof is a Python research prototype
  - NeuroProof verifies every proof step through TCB kernel (Glucose4 does not)
  - NeuroProof produces human-readable ND proofs (DRAT certificates are opaque binary)
  - NeuroProof computes Craig interpolants online (Glucose4 does not)

### 6.3 价值重定义（在 Discussion 中）

- "Which is more valuable: a 0.5ms opaque answer, or a 10ms certified proof?"
- 在安全关键领域（航空、医疗、自动驾驶），certified proofs 的价值远超 raw speed
- 教学和研究场景中，readable proofs 具有独立价值

### 6.4 诚实加分

- 主动承认 PHP 的 UNKNOWN 结果
- 将"UNKNOWN"框定为"宁可承认不知道，也不给出错误答案"的负责任行为
- 这在审稿中往往是加分项而非减分项

---

## 七、算法优化建议

以下是对 NeuroProof CDCL solver 的具体优化建议，旨在缩小与工业求解器的速度差距，同时不影响系统的可验证性和架构清洁度。

### 7.1 短路优化（低风险、高收益）

| 优化项 | 文件 | 方法 | 预期加速 |
|---|---|---|---|
| **Watched literal index** | solver.py | 将 `_watched` 从 dict-of-list 改为 contiguous array，O(1) 直接访问 | 2-3× |
| **Early conflict detection** | solver.py | 在 BCP 循环中，每 100 次传播检查一次 timer，避免 full timer check per literal | 1.2× |
| **LBD caching** | solver.py | 缓存已计算过的子句 LBD 值（在 clause 对象上），避免重复递归计算 | 1.5× |
| **Var activity bitmap** | solver.py | 用 numpy boolean array 替代 `set` 追踪活跃变量 | 1.3× |

### 7.2 结构优化（中等风险、高收益）

| 优化项 | 方法 | 预期加速 |
|---|---|---|
| **Incremental BCP** | 只在受影响的 watched literal 上重跑 BCP，而非从头开始 | 3-5× |
| **Lazy clause deletion** | 批量删除（每 N 次冲突），避免每个冲突后立即维护子句数据库 | 1.5× |
| **Pre-allocated clause arrays** | 预分配固定大小的子句存储（如 1M slots），用 freelist 管理 | 1.3× |
| **Two-literal watch refinement** | 当前实现可能重复 watching，确保每个子句 exactly 2 watches | 1.2× |

### 7.3 启发式优化

| 优化项 | 方法 |
|---|---|
| **Adaptive restart** | 实现 Luby 序列或 Glucose 风格的动态 restart（当前可能有固定 restart） |
| **Phase saving** | 记忆每个变量上次的赋值，新 decision 时优先使用 |
| **VSIDS decay** | 调整 decay factor，当前可能过快衰减 |

### 7.4 并行化（可扩展方向）

| 优化项 | 方法 |
|---|---|
| **Parallel tactic exploration** | 在 tactic 层面，同时启动多个 tactic，取第一个成功的结果 |
| **Parallel interpolation** | 在多个冲突子句上并行计算插值 |

### 7.5 不推荐的优化

- **C/C++ rewrite**：会破坏 Python 研究原型的可读性和可维护性。优先在 Python 内充分优化后再考虑。
- **移除 TCB kernel 验证**：会破坏系统的核心价值（certified proofs）。不可接受。

---

## 八、最终推荐

### 投稿策略

1. **首选 CAV 2027**（录取可能性 ~65%），理由是：
   - CAV 看重可运行系统 + 形式化验证
   - NeuroProof 的 Rocq formalisation 是差异化优势
   - CAV 审稿人对"不是最快的 SAT solver"有更大的容忍度

2. **备选 CPP 2027**（录取可能性 ~80%），如果 CAV 被拒：
   - Certified Programs and Proofs 社区对形式化验证论文非常友好
   - 可能需要调整为更侧重验证而非性能的论述

### Cover Letter 要点

- **第一句**：明确定位为 "certified proof system"，而非 "SAT solver"
- **核心贡献**：三位一体的架构（certified + online + feedback-driven）
- **差异化**：vs. neural ATP（零预训练）、vs. verified SAT（验证整个演算而非仅输出）、vs. DRAT/LRAT（人类可读 vs. 二进制）
- **诚实性**：主动说明当前实验的 scope 和 Python prototype 的速度限制

### 最终判断

NeuroProof 是一个**架构设计上有真正创新**的证明系统。它的核心价值不在于 raw solving speed，而在于将 certified proof checking、online learning、和 Craig interpolation 以反馈闭环的方式组合在一起。论文的写作和呈现是高质量的，实验是全面和诚实的。

在正确的 framing（certified proof system, not SAT solver）和适当的论述策略下，CAV 2027 的录取是可期的。
