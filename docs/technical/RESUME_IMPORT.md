# Local Resume Import V1

> 状态：Phase 10 contract frozen；实现中。真实 DOCX/PDF 内容质量必须由项目负责人验收。

## Boundary

流程固定为 `File → Parse → Preview → User Review → Confirm → Resume/Profile`。
Parse 不保存，Preview 不保存；只有“确认导入”写 SQLite。V1 只支持 10 MiB 以内的文字型 PDF 与
DOCX，不执行 OCR、宏、脚本、外部链接获取、LLM、改写、评分、生成或 Extension upload。

原文件只进入本机 loopback API 的内存解析过程，完成后不保存副本。文件名、正文、姓名、联系
方式和经历不进日志；允许的统计只有格式、字节数、PDF 页数、耗时和字符数。

## API contract

- `POST /api/v1/resume-imports/parse`：Web-only multipart，字段名 `file`；返回可编辑 preview，
  不写数据库。
- `POST /api/v1/resume-imports/confirm`：JSON-only；可提交 `resumeVersion`、`profileImport` 或
  两者，至少一项非空。

Parse 是现有 JSON-only mutation gate 的唯一 multipart 例外，仍要求 loopback Host、精确 Web
Origin 与非 cross-site Fetch Metadata。Extension Origin 不允许调用。Confirm 复用现有 JSON gate。

Preview 不返回或保存原始文件名，包含 `fileType`、`extractedText`、按顺序的 `blocks`、明确标题
切分的 `sections`、`profileCandidates`、`warnings` 与非敏感 `metrics`。

## Resource and parser limits

- 输入：10 MiB；extension、声明 MIME 和 magic/package structure 必须一致；
- PDF：最多 100 页、最多 100,000 字符、页间检查解析耗时；加密拒绝；少于 20 个非空白字符视为
  扫描件/图片型，不做 OCR；
- DOCX：限制 ZIP entry 数、单 entry/总解压大小和极端压缩比，拒绝路径穿越、macro content type、
  DTD/entity；外部 relationship 只记录忽略 warning，不发起请求；
- DOCX 按 body 顺序提取 paragraph 与 table row，PDF 按 page/line 顺序提取。

## Deterministic structure

只有完整行匹配批准 alias 才切 BASIC、EDUCATION、EXPERIENCE、PROJECT、SKILLS、CERTIFICATES、
AWARDS、OTHER。正文只出现“项目”等词不会切 section。phone/email 使用有界 regex；name 只在
靠近联系方式且形态明确时保守候选。教育/经历只提取原文明确写出的字段和月份，绝不推断学历、
毕业年份、培养年限、公司或职位；不确定内容保留在 section text。

## Confirm and merge

默认版本名为 `导入简历 YYYY-MM-DD`，不使用 filename。Web 可编辑版本名、正文和所有候选事实，
phone/email 默认遮罩并由用户主动展开编辑。

Profile import 是 patch-like command：只发送用户选择的 scalar 和新增 rows。服务端在事务内加载
当前 Profile，未选择 scalar 与所有既有 rows 原样保留。相同教育/经历只提示“可能重复”，不自动
删除；用户仍决定是否追加。Resume + Profile 使用一个 SQLAlchemy transaction，失败全部回滚。

## Stable errors

- `UNSUPPORTED_RESUME_FILE_TYPE`
- `RESUME_FILE_TOO_LARGE`
- `RESUME_FILE_SIGNATURE_MISMATCH`
- `RESUME_PDF_ENCRYPTED`
- `RESUME_PDF_NO_TEXT`
- `RESUME_PDF_INVALID`
- `RESUME_DOCX_INVALID`
- `RESUME_TEXT_TOO_LARGE`
- `RESUME_PARSE_TIMEOUT`

所有错误使用统一 JobPilot envelope，不包含 filename、正文、parser traceback 或原始 payload。
