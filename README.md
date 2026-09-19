# OSIS Check-Repair Six-Framework Comparison

本仓库是 OSIS 第二条实验任务线：对同一批“验算失败定位与修复”任务比较 T1–T6 六种智能体架构。
仓库公开实验代码、协议、测试和环境锁定信息；正式样本、种错工程、隐藏答案、原生 OSIS 文件、模型回复与实验结果全部留在仓库外或 Git 忽略目录。

## 六个实验架构

| ID | 架构 | 框架特征 |
| --- | --- | --- |
| T1 | Direct | 单次模型请求，无交互工具 |
| T2 | LangGraph | create_agent 流式 ReAct 与受限工具 |
| T3 | smolagents | CodeAgent / CodeAct |
| T4 | OpenHands | AgentSkills 原生渐进加载、Agent、Conversation |
| T5 | CrewAI | 诊断、修复、只读复核三角色顺序编排 |
| T6 | OSIS-AI | 隔离 OpenCode 工程中的原生工作流，独占串行运行 |

六个架构接收同一个公开任务、技能快照、模型、variant、预算和候选写入合同。正式 OSIS 验算与评分只由统一 runner 执行。

## 快速检查

安装基础与测试依赖：

    uv sync --python 3.13 --extra test
    uv run pytest -q
    uv run python scripts/audit_public_boundary.py

检查父仓库的新协议，不启动模型或 OSIS：

    uv run python scripts/run_dataset.py --architecture T2 --skills-dir tmp/check-repair-skill-snapshot --dry-run

创建不含模板答案的本地技能快照：

    uv run python scripts/create_skill_snapshot.py --parent-repo PATH_TO_PARENT

正式运行还需要专用 OSIS scratch 工程及其建模 Python。完整命令见 REPRODUCIBILITY.md。

## 数据边界

以下内容不得提交：datasets、seeded、private、candidate_project、runs、reports、OSISPost.out、LCC、日志、数据库、密钥与本机路径配置。发布前审计脚本会检查 Git 已跟踪文件和尚未忽略的新文件。

历史模型结果不随代码发布。复现者使用同一父仓库 commit、模型配置和 seed 重新执行实验，生成结果默认写入 runs 目录。

## 文档

- REPRODUCIBILITY.md：从零复现实验
- ENVIRONMENT.md：Python、OSIS 与 OpenCode 环境
- docs/框架使用说明.md：T1–T6 的实现与公平性
- docs/数据边界与发布审计.md：隐私边界和发布门禁
