# Resume Version V1

## Boundary

`ResumeVersion` 是用户在一个 JobPilot 本地 workspace 内主动创建的纯文本快照。V1 只支持
名称与正文的手动录入/粘贴；不读取文件，不解析 PDF/DOCX/图片，不做 OCR、富文本、模板或
自动改写。

正文按 untrusted plain text 处理：API 校验长度和控制字符，Web 只用普通文本节点/textarea
显示，测试只用虚构数据。正文只保存在 `runtime-data/jobpilot.db`；不进入 Extension、日志、
telemetry、错误、Git 或文档。

## Lifecycle

- 创建需要非空 `name` 和 `content`；服务端裁剪首尾空白并拒绝越界输入。
- PATCH 可独立修改名称或正文，`updatedAt` 随真实写入更新。
- duplicate 复制正文并使用用户提交的新名称，生成独立 id 与时间。
- 无 Application 引用时允许删除，并级联其 Evidence Map。
- 有任一 Application 引用时返回 `409 RESUME_VERSION_IN_USE`，不破坏历史。

## Application association

`applications.resume_version_id` nullable。创建 Application 时保持 null；用户必须在 Application
区明确选择、保存、更换或清空。选择只记录投递事实，不触发 Evidence Map，也不意味着 Evidence
Map 当前选择就是实际投递版本。
