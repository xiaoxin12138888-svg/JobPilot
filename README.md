# JobPilot

把岗位、简历、投递和面试记录放在一起的本地求职工作台。

通过 Chrome 插件保存 BOSS 直聘或牛客的岗位，在网页中管理求职进度；需要时，再使用 AI 辅助分析岗位、匹配简历和准备面试。

## 能做什么

- **保存岗位**：从当前打开的 BOSS / 牛客岗位页采集信息，预览确认后保存，并识别重复岗位。
- **跟踪投递**：记录投递状态、使用的简历版本、面试轮次和最终结果。
- **管理简历**：导入文字型 PDF / DOCX，预览后保存；按分区逐行查看和编辑，维护多个版本。
- **AI 求职助手**：提供岗位理解、简历匹配、简历建议和面试准备，展示结论引用的原文证据。
- **辅助填写表单**：维护求职资料，扫描招聘申请表，确认后填写支持的字段，最后由你检查并提交。
- **回顾求职过程**：汇总投递与面试记录，查看来源、简历版本和结果统计。

核心功能不需要注册账号或配置 AI。当前岗位采集支持 **BOSS 直聘、牛客**；简历导入暂不支持扫描件和 OCR，真实文档的解析与合并适配仍在持续验证。

## 快速开始

当前通过源码运行，需要 Git、Node.js 24.15+（24.x）、pnpm 11.19.0、Python 3.12、uv 和 Chrome。其他兼容 Node 版本见 [package.json](package.json)。

### 1. 下载并安装依赖

```powershell
git clone https://github.com/xiaoxin12138888-svg/JobPilot.git
cd JobPilot
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
```

### 2. 启动本机服务和网页

在项目目录打开两个终端，分别运行：

```powershell
pnpm run api:dev
```

```powershell
pnpm run dev:web
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。API 默认运行在 `127.0.0.1:8000`，首次启动会自动创建本地数据库。

停止服务时，在对应终端按 `Ctrl+C`。再次启动会继续使用已有数据。

### 3. 安装 Chrome 插件

```powershell
pnpm run build:extension
```

打开 Chrome 的 `chrome://extensions`，开启「开发者模式」，点击「加载已解压的扩展程序」，选择项目下的 `apps/extension/dist`。

保持本机 API 在 **8000 端口**运行。打开一个 BOSS / 牛客岗位详情页，点击插件，按「解析 → 预览 → 保存」完成采集。

## 可选：启用 AI

在启动 API 的终端中配置这三个环境变量，然后重启 API：

- `JOBPILOT_LLM_BASE_URL`：兼容 OpenAI 接口的服务地址。
- `JOBPILOT_LLM_API_KEY`：你的服务密钥。
- `JOBPILOT_LLM_MODEL`：模型名称。

未配置时，岗位、简历、投递与面试管理仍可正常使用。AI 服务的可用性和费用取决于你选择的提供方。配置细节见 [AI 配置与边界](docs/technical/JD_AI_ANALYSIS.md)，功能说明见 [AI 求职助手](docs/technical/AI_COPILOT.md)。

## 数据与隐私

业务数据保存在本机 `runtime-data/jobpilot.db`，没有 JobPilot 账号或云端同步；数据库与本地密钥配置不纳入 Git。

PDF / DOCX 在本机解析，原文件不持久化。只有你在生成 AI 内容前明确确认，当前任务所需的岗位、简历或面试文本才会发给你配置的第三方 AI 服务；发送前会移除电话和邮箱。请勿把 API Key 提交到仓库。

插件只在你主动操作时读取当前页面或填写已确认字段。投递、提交表单和发送消息始终由你完成。

## 项目文档

技术栈：React · TypeScript · Chrome Extension · FastAPI · SQLite。

- [产品说明](docs/PRODUCT_SPEC.md) · [开发进度与已知限制](docs/ROADMAP.md)
- [系统架构](docs/ARCHITECTURE.md) · [API 文档](docs/API_CONTRACT.md)
- [简历导入](docs/technical/RESUME_IMPORT.md) · [表单辅助填写](docs/technical/AUTOFILL.md)
- [AI 评测与验收记录](docs/evaluation/COPILOT_RESULTS.md)

AI Copilot 已通过当前阶段验收，其他模块的验证状态见开发进度。阶段历史、评测明细与技术决策保留在 `docs/` 中。
