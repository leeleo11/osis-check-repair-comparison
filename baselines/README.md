# Baseline adapters

所有 adapter 导出 run_generation(request)，并在 ignored workspace 写入 tN_generation.json。

| Adapter | 原生入口 | 能力边界 |
| --- | --- | --- |
| T1 | HTTP chat completion | 单次调用；候选与技能以固定文本包提供；只解析文件块 |
| T2 | LangGraph create_agent / stream | ReAct；技能读取与候选读写，与建模线同一工具面 |
| T3 | smolagents CodeAgent | `tools=[]`；`json` 与 `pathlib` 放行，模型自己读写 |
| T4 | OpenHands AgentContext / Conversation | 原生 AgentSkills；官方终端与文件编辑器；浏览器关闭 |
| T5 | CrewAI sequential Crew | 原生技能挂载与委派；官方文件工具；diagnoser、verifier 只读，repairer 可写 |
| T6 | 父仓库 check-repair agent | 调用 `chat_via_agent`；技能与工程都在父仓库 OpenCode 上；串行；评测无语法硬门禁 |

Adapter 不能读取 private staging、父仓库数据集、正式评分器或其他 run。它们可以读取统一技能快照和当前 candidate_project，并在允许的文本类型内写候选。官方 OSIS 验算只发生在 adapter 返回之后。
