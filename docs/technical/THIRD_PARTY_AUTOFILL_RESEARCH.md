# 第三方 Autofill 研究与许可记录

## 结论

Phase 9 当前实现为 JobPilot 原生实现，没有复制第三方源码。研究只用于理解常见 DOM autofill
边界；实际代码保持有限 Scanner/Resolver/Executor，而不是整体迁入通用 ATS Engine。

## JobFill

- Repository：`zhuanglaihong/JobFill`
- License：MIT
- Used as：架构与兼容思路参考
- Copied code：NO
- Attribution：N/A（当前无实质代码复制）

参考概念包括：Chrome MV3 用户触发、字段 alias、原生 setter/标准事件、native select、保守
combobox/date 处理。JobPilot 没有复制整个 content script，也没有采用 React Fiber、Phoenix
组件私有调用或其他框架内部 hook。若未来复制实质 MIT 代码，必须先在本文件列出 source file、
used portion、JobPilot target file，并随分发满足 MIT notice。

## jobApplier

- Repository：`17nbist/jobApplier`
- License：NO EXPLICIT LICENSE CONFIRMED
- Usage：architecture reference only
- Copied source：NO

仅参考 Scan / Resolve / Fill 分层、stable ref、unset = don't touch、review-before-fill 和 no-submit
原则。由于未确认明确许可，不复制任何源码、配置或 ATS 规则。

## 明确未采用

- 整体搬运 JobFill content script 或 jobApplier ATS engine；
- 50+ ATS 配置、Adapter registry、plugin runtime、workflow/action DSL；
- React Fiber、Vue private state、Phoenix private component API；
- AI Mapper、远程 parser、telemetry 或云 Profile；
- 自动 Submit、Continue、协议勾选、文件上传或验证码处理。
