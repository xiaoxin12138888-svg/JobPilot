# Local Resume Import V1

> 状态：Phase 10 实现、全量自动化与虚构文件隔离浏览器验收完成；真实 DOCX/PDF 内容质量和
> Profile 合并仍必须由项目负责人验收，尚未标记 PASS。

## Boundary

流程固定为 `File → Parse → Preview → User Review → Confirm → Resume/Profile`。
Parse 不保存，Preview 不保存；只有“确认导入”写 SQLite。V1 只支持 10 MiB 以内的文字型 PDF 与
DOCX，不执行 OCR、宏、脚本、外部链接获取、LLM、改写、评分、生成或 Extension upload。

原文件只进入本机 loopback API 的内存解析过程，完成后不保存副本。文件名、正文、姓名、联系
方式和经历不进日志；允许的统计只有格式、字节数、PDF 页数、耗时和字符数。

## API contract

- `POST /api/v1/resume-imports/parse`：Web-only multipart，只接受一个名为 `file` 的 part；额外字段
  或重复文件均拒绝。返回可编辑 preview，不写数据库。
- `POST /api/v1/resume-imports/confirm`：JSON-only；可提交 `resumeVersion`、`profileImport` 或
  两者，至少一项非空。

Parse 是现有 JSON-only mutation gate 的唯一 multipart 例外，仍要求 loopback Host、精确 Web
Origin 与非 cross-site Fetch Metadata。Extension Origin 不允许调用。Confirm 复用现有 JSON gate。

Preview 不返回或保存原始文件名，包含 `fileType`、`extractedText`、按顺序的 `blocks`、明确标题
切分的 `sections`、`profileCandidates`、`warnings` 与非敏感 `metrics`。

## Resource and parser limits

- 输入文件：10 MiB；multipart 总请求在解析前限制为文件上限加 64 KiB 协议开销，缺失/畸形长度
  或超限请求直接拒绝；文件读取后再精确检查 10 MiB；extension、声明 MIME 和
  magic/package structure 必须一致；
- PDF：最多 100 页、最多 100,000 字符、10 秒有界解析时间并在页间检查；加密拒绝；少于 20 个
  非空白字符视为扫描件/图片型，不做 OCR；少于 200 个非空白字符提示 `PDF_TEXT_SHORT`；
- DOCX：最多 1,000 个 ZIP entry、单 entry 解压后最多 20 MiB、总解压后最多 50 MiB、压缩比最多
  200，拒绝路径穿越、macro content type、DTD/entity；外部 relationship 只记录
  `EXTERNAL_RELATIONSHIP_IGNORED`，不发起请求；检测到表格时提示 `TABLE_ORDER_REVIEW`；
- DOCX 按 body 顺序提取 paragraph 与 table row，PDF 按 page/line 顺序提取。

## Deterministic structure

只有完整行匹配批准 alias 才切 BASIC、EDUCATION、EXPERIENCE、PROJECT、SKILLS、CERTIFICATES、
AWARDS、OTHER。正文只出现“项目”等词不会切 section。phone/email 使用有界 regex；name 只在
靠近联系方式且形态明确时保守候选。教育/经历优先读取明确标签；常见 `|` 分隔表格行只有同时
存在可识别学校/公司与明确月份时才保守生成候选。绝不推断学历、毕业年份、培养年限、公司或
职位；不确定内容保留在 section text。

## Confirm and merge

默认版本名为 `导入简历 YYYY-MM-DD`，不使用 filename。Web 可编辑版本名、正文和所有候选事实，
phone/email 默认遮罩并由用户主动展开编辑。

Profile import 是 patch-like command：只发送用户选择的 scalar 和新增 rows。Web 明确列出当前
教育/经历的事实内容和导入候选，而不是只显示计数。服务端在事务内加载当前 Profile，未选择
scalar 与所有既有 rows 原样保留。相同教育/经历只提示“可能重复”，不自动删除；用户仍决定
是否追加。Resume + Profile 使用一个 SQLAlchemy transaction，失败全部回滚。

## Dependencies and license review

| Dependency | Locked version | License | Purpose |
| --- | --- | --- | --- |
| `pypdf` | 6.17.0 | BSD-3-Clause | 本地文字型 PDF 提取、页数与加密状态读取 |
| `python-docx` | 1.2.0 | MIT | 本地 DOCX paragraph/table 读取 |
| `python-multipart` | 0.0.32 | Apache-2.0 | FastAPI 单文件 multipart 请求解析 |
| `lxml` | 6.1.3 | BSD-3-Clause | `python-docx` 锁定的 XML 运行依赖 |

未加入 GPL/AGPL dependency；未复制 OpenResume 源码。上述许可证来自本地安装包 metadata，版本
来自 `apps/api/uv.lock`。

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

## Fictional isolated browser acceptance

2026-09-07 使用独立临时 SQLite、未配置 Provider 和全虚构文件完成浏览器验收，不接触真实用户
数据：PDF 为 1,208 bytes、2 页、228 字符，UI 记录 0 ms；DOCX 为 37,037 bytes、189 字符，首次
31 ms，API 重启后重复解析 16 ms。PDF Parse 后取消时 Resume/Profile 均未写入；DOCX Confirm
创建“浏览器验收简历”并只写入所选姓名、联系方式、教育与经历，API 重启后仍存在。

重复 DOCX 导入会显示现有教育/经历事实、标注可能重复并默认不选；`<img
src=x onerror=alert(1)>` 仅作为 textarea 文本，DOM 未创建 `img`；`.txt` 显示仅支持 PDF/DOCX；
320/768/1024/1440 均无横向溢出，console error/warning 为 0。以上只证明虚构 fixture 的技术链路，
不进入 Real Bad Cases，也不替代项目负责人对真实脱敏 DOCX/PDF 的内容质量判断。
