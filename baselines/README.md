# Baseline adapters

所有 adapter 导出 run_generation(request)，并在 ignored workspace 写入 tN_generation.json。

| Adapter | 原生入口 | 能力边界 |
| --- | --- | --- |
| T1 | HTTP chat completion | 单次调用；候选与技能以固定文本包提供；只解析文件块 |
| T2 | LangGraph create_agent / stream | ReAct；共享受限工具 |
| T3 | smolagents CodeAgent | CodeAct；共享受限工具与窄执行环境 |
| T4 | OpenHands AgentContext / Conversation | 原生 AgentSkills 渐进调用；候选工具；精简 hand-off |
| T5 | CrewAI sequential Crew | diagnoser 只读、repairer 可写、verifier 只读 |
| T6 | OpenCode / OSIS-AI | 每条 run 的隔离原生工程；完整原生会话；串行 |

Adapter 不能读取 private staging、父仓库数据集、正式评分器或其他 run。它们可以读取统一技能快照和当前 candidate_project，并在允许的文本类型内写候选。官方 OSIS 验算只发生在 adapter 返回之后。
