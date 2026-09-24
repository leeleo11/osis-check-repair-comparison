# OSIS Check-Repair Six-Framework Comparison

本仓库是 OSIS 第二条实验任务线：对同一批“验算失败定位与修复”任务比较 T1–T6 六种智能体架构。
仓库公开实验代码、协议、测试和环境锁定信息；正式样本、种错工程、隐藏答案、原生 OSIS 文件、模型回复与实验结果全部留在仓库外或 Git 忽略目录。

## 六个实验架构

| ID | 架构 | 框架特征 |
| --- | --- | --- |
| T1 | Direct | 单次模型请求，无交互工具 |
| T2 | LangGraph | `create_agent` 流式 ReAct；调用方传入与建模线相同的技能读取和候选读写工具 |
| T3 | smolagents | `CodeAgent`，`tools=[]`；解释器放行 `json`、`pathlib`，自己读写文件 |
| T4 | OpenHands | 原生 `invoke_skill`；官方终端、文件编辑器和任务跟踪；浏览器关闭 |
| T5 | CrewAI | `Crew(skills=...)`，允许委派；官方文件工具；诊断与复核只读，修复者可写 |
| T6 | OSIS-AI | 父仓库指令；只挂无模板快照；串行 |

T1–T6 使用同一份去掉 `templates/` 的技能快照和同一份候选工程。模板是种错前的正确工程，留在技能里等于把答案交给模型。正式 OSIS 验算与评分只由统一 runner 执行。

## 快速检查

安装基础与测试依赖：

    uv sync --python 3.13 --extra test
    uv run pytest -q
    uv run python scripts/audit_public_boundary.py

检查父仓库的新协议，不启动模型或 OSIS：

    uv run python scripts/run_dataset.py --architecture T2 --skills-dir tmp/check-repair-skill-snapshot --dry-run

创建技能快照。桥型 `templates/` 会整段去掉，其余技能文件保留：

    uv run python scripts/create_skill_snapshot.py --parent-repo PATH_TO_PARENT

正式运行还需要专用 OSIS scratch 工程及其建模 Python。完整命令见 REPRODUCIBILITY.md。

## 数据边界

以下内容不得提交：datasets、seeded、private、candidate_project、runs、reports、OSISPost.out、LCC、日志、数据库、密钥与本机路径配置。发布前审计脚本会检查 Git 已跟踪文件和尚未忽略的新文件。

历史模型结果不随代码发布。复现者使用同一父仓库 commit、模型配置和 seed 重新执行实验，生成结果默认写入 runs 目录。

## 文档

- REPRODUCIBILITY.md：从零复现实验
- ENVIRONMENT.md：Python、OSIS 与 OpenCode 环境
- docs/框架使用说明.md：怎么开跑、并行或串行、T1–T5 各自怎么读技能和写候选
- docs/数据边界与发布审计.md：隐私边界和发布门禁
