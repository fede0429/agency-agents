# Agency Agents — 项目风控策略

这是本项目唯一的高风险策略源。所有 agent 操作必须遵守本文件，与全局 GEMINI.md 冲突时以本文件为准。

---

## 硬性禁止（任何情况下不得执行，无例外）

- 禁止读取或修改 `core/platform_credential_center.py` 管理的 `credentials.json` 文件内容
- 禁止将任何平台 token（douyin / xiaohongshu / tiktok / youtube）写入代码或日志
- 禁止调用 `direct_publish_skeleton.py` 中任何触发实际发布的函数（非 dry-run）
- 禁止修改 `bot/telegram_handler.py` 中的消息接收和指令解析逻辑，除非明确告知影响范围
- 禁止在没有速率限制保护的情况下批量调用外部 AI API（防止意外计费）

---

## 需要人工审批后才能执行

- 触发向任意平台（抖音 / 小红书 / TikTok / YouTube）的内容发布流程
- 修改 `orchestrator.py` 中的多 agent 调度逻辑
- 修改 `hook_score_engine.py` 中的评分权重
- 修改 API 调用的计费相关参数（模型、token 上限、并发数）
- 修改 Telegram bot 的指令白名单

---

## 发布操作规范

调用任何发布相关函数前，必须确认：
1. 当前是 dry-run / preview 模式还是真实发布
2. 目标平台账号是否正确（多账号环境下容易误发）
3. 内容是否已通过 `hook_score_engine` 评分且分值达标

---

## 失败处理

执行失败时必须输出：
- 失败类别：`publish_failure` / `credential_failure` / `api_quota_failure` / `validation_failure`
- 已触碰的文件列表
- 是否需要人工介入
