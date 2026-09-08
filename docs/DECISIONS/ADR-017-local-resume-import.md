# ADR-017：本地 PDF / DOCX 简历导入

- **Status**：Accepted
- **Date**：2026-09-07
- **Decision owner**：JobPilot 项目负责人

## Context

JobPilot 已有纯文本 `ResumeVersion` 与 singleton `AutofillProfile`，但已有 PDF / DOCX 简历仍需
手工复制正文和重复填写结构化资料。Phase 10 需要在不依赖 LLM、不保存原始文件且不污染现有
数据的前提下，把本地文件提取、确定性结构识别、人工预览和最终写入分开。

PDF、DOCX、文件名和提取文本均是不可信私密输入。DOCX 是 ZIP/XML container，PDF parser 也可能
面对加密、损坏或资源消耗型文件；导入入口必须同时限制格式、大小、解压资源、页数和文本量。

## Decision

1. Phase 10 只支持用户在 Web 主动选择的 `.pdf` 与 `.docx`，单文件上限固定为 10 MiB。文件只发往
   精确 loopback FastAPI，不进入 Extension、Provider、telemetry、Git 或普通日志。
2. `POST /api/v1/resume-imports/parse` 是无状态 multipart parse command。它验证 extension、声明的
   MIME 与文件 magic/package structure，返回 file type、按阅读顺序提取的纯文本/blocks、确定性
   sections、Profile candidates、warnings 及非敏感统计；不写 SQLite。它是现有 JSON-only write
   gate 的唯一 multipart 例外，并且只允许合法 loopback Web Origin，Extension 不受信任。
3. PDF 使用维护中的本地 parser，只支持可选择文本的文件。加密文件返回
   `RESUME_PDF_ENCRYPTED`；有效文字少于 20 个非空白字符返回 `RESUME_PDF_NO_TEXT`，不执行 OCR。
   最多解析 100 页、最多保留 100,000 字符，并在页之间执行有界耗时检查。
4. DOCX 使用维护中的本地 parser，按 document body 顺序提取 paragraph 与 table row。解析前检查
   ZIP 路径、entry 数、单 entry/总解压大小、压缩比、必需 package parts、macro content type、
   XML DTD/entity 与 external relationships；不执行宏、脚本或外部获取。损坏或危险 package 返回
   `RESUME_DOCX_INVALID`。
5. 文档提取与简历结构识别是两个模块。结构识别只在明确 heading alias 处切分 BASIC、EDUCATION、
   EXPERIENCE、PROJECT、SKILLS、CERTIFICATES、AWARDS、OTHER；只确定性提取 phone/email、保守
   name、明确日期及高置信教育/经历字段。不能确认的内容留在原始 section/block，不推断学历、
   毕业年份、培养年限、公司或职位。
6. Web 必须在写入前展示可编辑的导入预览：Resume name/text、sections、warnings、候选个人资料、
   教育和经历。phone/email 默认遮罩；用户可显式展开编辑。默认版本名为
   `导入简历 YYYY-MM-DD`，不持久化原始文件名。
7. `POST /api/v1/resume-imports/confirm` 保持 JSON-only。请求可选择创建 Resume Version、导入
   Profile 或同时执行，至少选择一项。Profile command 只携带用户明确选择的 scalar updates 与
   education/experience additions；服务端在事务内读取当前 Profile，保留所有未选择值和既有行。
8. Web 对 scalar 显示 Current vs Imported；当前为空时可默认选择 imported，不同非空值默认不选。
   数组只追加用户选择的 imported rows；标准化 school+major+start+end 或
   company+position+start+end 相等时提示“可能重复”，但不自动删除或合并。
9. Resume-only、Profile-only 与两者同时确认复用现有表。两者同时写入必须使用一个 SQLAlchemy
   transaction；任一失败全部回滚。导入不覆盖、删除或重命名已有 Resume Version，也不修改 Job、
   Application、Evidence Map 或 Phase 9 Autofill 行为。
10. 生产代码不保存原始文件副本，不记录原文件名、正文、姓名、联系方式或经历。允许记录/返回的
    诊断仅为稳定 error code、file type、字节数、PDF 页数、耗时和提取字符数。
11. 新增依赖必须锁定并记录许可证。GPL/AGPL 依赖或 OpenResume 源码不得进入项目；Phase 10 不使用
    OCR、LLM、RAG、Embedding、Agent、Resume Builder/Generator/Tailoring 或 Extension upload。
12. 自动化与隔离浏览器完成后，真实 DOCX/PDF 内容质量、持久化和 Profile 合并必须由负责人使用
    脱敏文件人工确认。在确认前只能报告
    `USER ACTION REQUIRED — REAL RESUME IMPORT ACCEPTANCE`，不能宣布 Phase 10 PASS。

## 2026-09-08 owner amendment

真实 DOCX 预览证明 PROJECT section 正文完整但没有结构化候选。负责人批准把项目经历作为独立
`projects[]` 加入 Profile 与 Phase 10 Preview/Confirm：字段固定为 `name`、`role`、`start`、`end`、
`description`；只解析明确 PROJECT section 中以月份范围开头的项目头，描述仅拼接该项目头之后、
下一个项目头之前的原文。候选可编辑，Confirm 只追加勾选行并保留现有项目；可能重复只提示。

该增量使用可逆 migration 为 singleton Profile 增加 `projects_json` 并把既有数据回填为空数组。
Extension Autofill 不消费项目字段，不增加字段映射、页面写入、权限或提交能力；其余 Phase 9/10
安全、隐私、Parse != Save、无 Provider/OCR/远端依赖及 Phase 11 stop 条件不变。

## Consequences

- 不新增 ResumeImport 表或 migration；preview 生命周期只存在于 Web 内存。
- 无状态 Parse 与 patch-like Confirm 避免临时文件/会话清理，并使未选择的 Profile 数据在并发页面
  更新后仍能由服务端保留。
- 确定性 parser 会保守漏识别复杂排版，但 raw-text fallback 仍允许创建可编辑 Resume Version。
- 扫描件和图片型 PDF 需要用户改用文字型 PDF/DOCX；V1 不通过远端或 AI 降级。
