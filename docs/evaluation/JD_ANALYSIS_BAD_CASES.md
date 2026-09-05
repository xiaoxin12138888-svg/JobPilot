# JD 分析 Prompt V1 Bad Cases

## 记录依据

以下案例只来自 `jd-analysis/prompt-v1-run.json` 的 20/20 真实 validated outputs，并逐条与
冻结的 `dataset-v1.json` Gold 比对。Gold、Prompt V1、Schema 和评分算法均未修改。

## 主要真实 Bad Cases

### BC-01：加分项限定词被系统性删除

- 影响：15/20 个样本；正式指标为 Preferred Omissions 16、Preferred False Extractions 16。
- 例子：`jd-003` 的 Gold 是“有零售行业分析经验加分”，实际是“有零售行业分析经验”；
  `jd-020` 的“持证者优先”“有政企项目经历更佳”被改写为“持有 PMP 证书”“有政企项目经历”。
- 原因：模型依赖 `preferredRequirements` 字段位置表达“加分项”，生成 `text` 时又做摘要，
  没有保留“优先/加分/更佳”等原文强度限定词。
- 影响判断：字段分类正确，Must-have/Preferred 交叉误分类仍为 0；但自包含文本的条件强度发生
  变化，并被冻结的 exact-match 评分如实记为遗漏和误提取。

### BC-02：硬性学历要求只进入专用字段，未保留在 Must-have

- 影响：`jd-006` 遗漏“本科及以上”“电子或计算机相关专业”；`jd-014` 遗漏“临床医学或
  药学硕士”，合计造成 3 条 Must-have omission。
- 实际：这些内容均存在于 `educationRequirements` 且 evidence 有依据，但没有出现在
  `mustHaveRequirements`。
- 原因：Prompt V1 没有说明 `mustHaveRequirements` 与 `educationRequirements` 是可重叠视图，
  模型把它们当成互斥分类并把学历要求移出了总硬性要求列表。

### BC-03：同一原文条目的拆分/合并粒度不稳定

- 职责例子：`jd-006` 把“开发外设驱动并定位量产问题”拆成两项；`jd-011` 和 `jd-019`
  也把 Gold 的一个并列职责拆成多个条目。
- 硬性要求例子：`jd-003`、`jd-008`、`jd-009`、`jd-015` 把 Gold 的并列能力要求拆成两项；
  `jd-007` 则把两个学历条目合成一项。
- 原因：Prompt V1 只要求“区分”和“不重复”，没有定义 item boundary。模型按语义原子化，
  Gold 则按固定的原文子句边界计分，导致语义大体保留但 exact-match 同时出现 omission 与
  false extraction。

### BC-04：文本改写破坏精确忠实度

- 例子：`jd-002`、`jd-010` 删除数字与英文之间的空格；`jd-016` 将“法学本科及以上”改写为
  “法学本科及以上学历”，将“具备良好书面表达”改写为“具备良好书面表达能力”；`jd-020`
  删除了“必须”。
- 原因：`text` 在 V1 中是可摘要字段，只有 `evidence` 被要求使用简短原文。模型因此生成了
  语义近似文本，而冻结 evaluator 对 `text` 做 exact-match。
- 影响判断：这些差异多数不是 hallucination；Evidence Grounding 仍为 183/183，但抽取文本
  不满足当前 Gold 的精确忠实度目标。

### BC-05：明确的“无要求”描述被写进专用要求数组

- `jd-017`：Gold `educationRequirements=[]`，实际输出“不限制专业和学历”。
- `jd-018`：Gold 的学历和经验数组均为空，实际输出“未限定学历”和“未限定工作年限”。
- 原因：Prompt V1 规定“缺失项返回空数组”，但没有明确说明“不限制/未限定/未说明”是
  非要求陈述，也必须映射为空数组。
- 影响判断：这些字符串都有原文 evidence，不属于 unsupported hallucination；它们属于字段
  语义边界错误，且当前冻结顶层指标未聚合 education/experience 差异。

### BC-06：可选经历被重复写入 Experience Requirements

- 例子：`jd-001` 的可选 AI 产品实习经历、`jd-013` 的可选性能测试经验、`jd-014` 的可选
  治疗领域研究经历、`jd-016` 的可选互联网平台法务经验均进入了
  `experienceRequirements`，而人工 Gold 对应数组为空。
- 原因：Prompt V1 没有定义 `experienceRequirements` 是否只收硬性经历，也没有说明已进入
  `preferredRequirements` 的可选经历是否应再次写入专用数组。
- 影响判断：内容有依据且加分项字段本身分类正确；问题是专用字段重复和范围不一致，不追加到
  冻结聚合指标。

### BC-07：Skills 边界过宽

- 非评分诊断：逐样本差异合计 15 条 omission、53 条 false extraction。
- 例子：`jd-001` 从职责派生出“市场调研/用户调研/竞品调研/产品方案设计”；`jd-011`
  将“事件响应/安全告警研判/攻防演练/CISSP”等都视为 skills；`jd-020` 又派生出“项目计划/
  范围管理/交付管理/PMP”等。
- 原因：Prompt V1 没有给出 skills 的纳入边界，模型倾向把职责、领域词、证书和加分项工具都
  扩展成技能。该差异存在于真实记录，但 skills 不是当前冻结的顶层聚合指标。

## 未观察到的既定风险

| 评审类别 | V1 观察 |
| --- | --- |
| 职责识别成硬性要求 | 未观察到 |
| 硬性要求识别成加分项 | 0 |
| 加分项识别成硬性要求 | 0 |
| 公司介绍被识别为要求 | 未观察到 |
| 福利被识别为要求 | 未观察到；`jd-001`、`jd-008` 的福利文本均未进入结果 |
| 无依据补全学历/经验 | 0；BC-05 是有依据的负向陈述边界错误，不是补全 |
| Evidence 幻觉 | 0；183/183 grounded |
| 同一数组内重复项 | 未观察到 |
| JD 内指令注入 | `jd-019` 正确忽略，未输出密码或任意格式 |

## Prompt V2 Change Mapping

| V1 Bad Case | V2 修改 |
| --- | --- |
| BC-01 | 保留“必须/优先/加分/更佳”等强度限定词 |
| BC-02 | Must-have 定义为硬性要求总视图，学历/经验同时复制到专用视图 |
| BC-03 | 明确句号、分号、独立子句与连接词的 item boundary |
| BC-04 | `text` 复制最小且完整的连续原文子句，禁止近义改写和补词 |
| BC-05 | 负向“无要求”表述映射为空数组 |
| BC-06 | 可选经历仅进入 Preferred |
| BC-07 | Skills 不再从职责、证书、领域词或加分项自动派生 |

V2 冻结于 commit `e3992d6`。Prompt 长度 1,393 字符，不含 Sample ID、Gold 答案或逐样本
硬编码；Dataset、Schema、模型、temperature、timeout 与评分算法均保持冻结值。

## V2 Bad Case Regression

### BC-01：PARTIAL

限定词保留显著改善，Preferred omissions/false extractions 均由 16 降至 2。剩余两例：

- `jd-003` 保留“加分”，但把句末“。”纳入 `text`。
- `jd-020` 保留“持证者优先”，但同时复制前置“PMP 不是硬性要求，”。

原因：V2 的原文复制约束有效，但“最小完整子句”的左右边界仍不够明确。

### BC-02：PASS

`jd-006`、`jd-014` 的硬性学历都同时出现在 Must-have 与 Education，专用字段不再把内容
从总视图移走。它们仍因“要求”前缀或合并粒度造成 exact-match 差异，该问题计入 BC-03/04。

### BC-03：PARTIAL

- V1 的 `jd-006`、`jd-011`、`jd-019` 职责拆分问题已修复。
- V2 新增 `jd-003` 将两个职责连同句号合并为一项，`jd-004` 将前两个职责合并为一项。
- `jd-007` 仍将“硕士及以上学历，计算机相关专业”合并。

Responsibilities false extractions 8→4，但 omissions 4→6；边界稳定性仅部分改善。

### BC-04：PARTIAL

V2 明显减少了删除空格、删除限定词和自由改写，但又出现两类真实问题：

- 15 个 Must-have `text` 保留了段落引导词“要求/需”，而 Gold 从实际要求内容开始。
- `jd-005` 将原文“与产品和研发协作”输出为“与产品 and 研发协作”，属于新的无依据语言改写。

Must-have false extractions 19→17，但 omissions 18→19，未形成全面改善。

### BC-05：PASS

- `jd-017` 的“不限制专业和学历”没有进入 Education。
- `jd-018` 的“未限定学历和工作年限”没有进入 Education/Experience。

负向陈述本身已正确映射为空。Evidence 继续保持全部 grounded。

### BC-06：PASS

V1 中 `jd-001`、`jd-013`、`jd-014`、`jd-016` 的可选经历在 V2 均只保留于 Preferred，
没有再次进入 Experience。

另有两个不属于原 BC-06 的人工观察：`jd-005` 将硬性作品集写入 Experience，`jd-018` 按
V2“硬性项目经验”规则写入 Experience，但二者的冻结 Gold 数组为空。它们不属于顶层正式指标，
本轮不修改 Prompt、Gold 或评分规则。

### BC-07：PARTIAL

Skills false extractions 从 53 降至 6，说明过度派生明显收敛；同时 omissions 从 15 升至 23，
表明约束过强并产生漏提取。代表例子：

- `jd-010` 输出空 Skills，Gold 的组织诊断、人才盘点、劳动法规均遗漏。
- `jd-016` 输出空 Skills，Gold 的合同审核和法律咨询均遗漏。
- `jd-020` 输出空 Skills，Gold 的项目管理和风险管理均遗漏。

## V2 新增观察

1. 原文忠实规则容易把段落标签“要求/需”和句末标点一起复制；需要未来单独决定是否存在 V3，
   本轮不得继续改 Prompt。
2. 更严格的 Skills 禁止派生规则以降低 47 条 false extraction 为代价，新增 8 条 omission。
3. `jd-005` 的“和”→“and”表明 `text` 仍可能与 grounded evidence 不一致；当前
   hallucination 指标只计算 evidence，不会捕获这种 text 改写。
4. 硬性“项目经验”应否进入 Experience 与 `jd-018` 冻结 Gold 存在解释差异，但不影响本轮
   已冻结的正式顶层指标；Gold 保持原样。

## V2 安全回归

| 风险 | 结果 |
| --- | --- |
| Schema strict validation | PASS，20/20 |
| Evidence grounding | PASS，181/181 |
| Unsupported hallucination | PASS，0 |
| Must-have/Preferred 互换 | PASS，0/0 |
| 福利进入要求 | PASS，`jd-001/008` 未提取 |
| Negative requirement | PASS，`jd-017/018` |
| Prompt injection | PASS，`jd-019` 未执行或复述恶意指令 |
| 同一数组重复项 | 未观察到 |

V2 已完成唯一一轮真实评测。即使仍有错误，本轮也不创建或运行 Prompt V3。
