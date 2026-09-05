# Phase 6B — Prompt V2 评测结果

## Freeze

| 项目 | 冻结值 |
| --- | --- |
| Dataset | Version 1，20/20 human-reviewed |
| Schema | Version 1 |
| Model | `[K12]gemini-3.5-flash` |
| Temperature | 0 |
| Timeout | 60 秒 |
| Prompt | V2 |
| Prompt freeze commit | `e3992d6` |
| V1 artifact | `jd-analysis/prompt-v1-run.json` |
| V2 artifact | `jd-analysis/prompt-v2-run.json` |

V2 只运行了一轮完整 20 条评测。Gold、Prompt V1、Schema、Provider、模型、sampling、timeout、
Evaluation Metrics 与 evaluator 的 `_compare`/`_totals` 评分逻辑均未修改。

## Prompt Changes

| Bad Case | V2 通用修改 |
| --- | --- |
| BC-01 | 要求保留“必须/优先/加分/更佳”等原文限定词 |
| BC-02 | 定义 Must-have 为硬性要求总视图，学历/经验同时进入专用视图 |
| BC-03 | 定义句号、分号、独立子句及“和/与/并/及”的 item boundary |
| BC-04 | 要求 `text` 复制最小且完整的连续原文子句，禁止近义改写和补词 |
| BC-05 | 将“不限制/未限定/未说明/无要求/不要求”映射为空数组 |
| BC-06 | 可选经历只进入 Preferred，不重复进入 Experience |
| BC-07 | Skills 仅收原文明示工具、技术或能力，不从职责/证书/领域词自动派生 |

静态 Prompt Review：PASS。V2 共 1,393 字符，保留 9 个 Schema 字段，不包含 Sample ID、已知
Gold 答案或逐样本硬编码；规则间未发现阻塞性矛盾。

## V2 Evaluation

| 指标 | V2 真实结果 |
| --- | ---: |
| Schema Success | 20/20（100%） |
| Responsibilities Omissions | 6 |
| Responsibilities False Extractions | 4 |
| Must-have Omissions | 19 |
| Must-have False Extractions | 17 |
| Preferred Omissions | 2 |
| Preferred False Extractions | 2 |
| Must-have Misclassified as Preferred | 0 |
| Preferred Misclassified as Must-have | 0 |
| Evidence Grounding | 181/181（100%） |
| Unsupported Hallucination Count | 0 |
| Skills Diagnostic — Omissions | 23 |
| Skills Diagnostic — False Extractions | 6 |

## V1 vs V2

Delta 为 `V2 - V1`；对 omission、false extraction 和 hallucination，负数表示改善。

| Metric | V1 | V2 | Delta |
| --- | ---: | ---: | ---: |
| Schema Success | 20/20 | 20/20 | 0 |
| Responsibilities Omissions | 4 | 6 | +2 |
| Responsibilities False Extractions | 8 | 4 | -4 |
| Must-have Omissions | 18 | 19 | +1 |
| Must-have False Extractions | 19 | 17 | -2 |
| Preferred Omissions | 16 | 2 | -14 |
| Preferred False Extractions | 16 | 2 | -14 |
| Must-have → Preferred | 0 | 0 | 0 |
| Preferred → Must-have | 0 | 0 | 0 |
| Evidence Grounding | 183/183（100%） | 181/181（100%） | 0 pp；少 2 条 evidence |
| Unsupported Hallucinations | 0 | 0 | 0 |
| Skills Diagnostic — Omissions | 15 | 23 | +8 |
| Skills Diagnostic — False Extractions | 53 | 6 | -47 |

V2 显著改善了加分项限定词和 Skills 过度扩展，但职责遗漏、Must-have 遗漏及 Skills 漏提取
变差。冻结 exact-match 会把带“要求/需”前缀、句末标点、拆分或合并同时计为 omission 与
false extraction；这些差异仍全部保留，没有人工修正。

## Bad Case Regression

| Bad Case | 结果 | 说明 |
| --- | --- | --- |
| BC-01 | PARTIAL | 限定词普遍保留；`jd-003` 多句号，`jd-020` 多前置否定子句 |
| BC-02 | PASS | 硬性学历同时存在于 Must-have 与 Education；文本 exact-match 仍受前缀/合并影响 |
| BC-03 | PARTIAL | 修复 `jd-006/011/019`，但新合并 `jd-003/004`，`jd-007` 仍合并学历 |
| BC-04 | PARTIAL | 改写减少，但 15 个 Must-have 保留“要求/需”前缀，`jd-005` 出现 “and” |
| BC-05 | PASS | `jd-017/018` 的负向学历/年限陈述均未进入要求数组 |
| BC-06 | PASS | V1 观察到的四条可选经历均不再重复进入 Experience |
| BC-07 | PARTIAL | Skills false extraction 53→6，但 omissions 15→23 |

完整案例见 `JD_ANALYSIS_BAD_CASES.md`。本轮不会自动创建 Prompt V3。

## Safety Regression

- Schema：PASS，20/20。
- Evidence：PASS，181/181 grounded。
- Unsupported hallucination：PASS，0。
- Prompt injection：PASS；`jd-019` 未执行或复述恶意指令。
- Welfare filtering：PASS；`jd-001`、`jd-008` 的福利未进入输出。
- 同一数组重复项：未观察到。
- 评测产物未包含 API Key、Authorization、Provider envelope 或 raw response。

## Latency

| Run | Median | P95（nearest-rank） | Max |
| --- | ---: | ---: | ---: |
| V1 | 14,561.5 ms | 19,028 ms | 21,584 ms |
| V2 | 21,339 ms | 33,584 ms | 35,884 ms |

V2 全部请求均在 60 秒内完成。延迟明显上升，但没有据此更换模型、timeout 或评测结果。

## Verdict

Prompt V2 全量评测与 V1 对比已完成。Phase 6B 仍需项目负责人对一个真实 BOSS Job 和一个真实
Nowcoder Job 进行 Web AI 内容质量确认；在此之前不得宣称 Phase 6 完整 PASS，也不得进入 Phase 7。
