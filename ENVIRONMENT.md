# Environment

## Python layers

- 主环境：Python 3.13，runner、T1、T2 和公开测试。
- T3 环境：smolagents 1.26 系列。
- T4 环境：OpenHands SDK 1.44 系列。
- T5 环境：CrewAI 1.15 系列。
- T6 与原生验算：父仓库已经在运行的 OpenCode（默认 `http://127.0.0.1:4096`）、父仓库 Python、pyosis 和本机 OSIS 引擎。本仓库不另起 OpenCode，也不改它的权限。

执行以下命令查看将创建的环境，不做修改：

    uv run python scripts/setup_framework_envs.py --dry-run

去掉 dry-run 后创建 .venv 与 .venvs/t3、t4、t5。所有目录均被 Git 忽略。

## Required environment variables

- OSIS_PARENT_REPO：父仓库路径，可由命令参数或 local 配置替代。
- OSIS_MODEL_API_KEY：模型网关密钥。
- OSIS_MODEL_BASE_URL：OpenAI compatible 网关地址。
- 父仓库 OpenCode 须已按父仓库验算修复评测的方式启动。T6 使用父仓库默认地址 `http://127.0.0.1:4096`，不读取 `OPENCODE_EXE` 或 `T6_AI_PORT`。

密钥不写入 adapter_request、manifest、报告或 Git 文件。

## OSIS native assumptions

正式验算器先把候选 py 树复制到专用 scratch 工程，执行 prep/main.py，再调用 OSISEngine.solve。若样本附带 OSISPost.out，则输入该文件后执行 CheckSolve；否则执行 checkdel,all 与 CombinationAndCheck。旧 Check LCC 和 Temperary TXT 会在每次验算前清理。

OSIS 是有状态的本机运行时。不要让两个正式验算并行使用同一个 scratch 工程。
