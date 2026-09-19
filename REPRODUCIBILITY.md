# Reproducibility

## 1. 固定源码

记录本仓库 commit 和父仓库 commit。父仓库必须包含 datasets/check_repair/samples.json、对应 seeded 工程、最新 score.py、ngutil.py 与 OSIS/OpenCode 运行环境。

复制本机配置模板：

    Copy-Item configs/parent_repo.example.txt configs/parent_repo.local.txt

将 local 文件中的路径改为父仓库路径。该文件被 Git 忽略。

## 2. 安装环境

基础环境：

    uv sync --python 3.13 --extra test --extra t2

框架隔离环境：

    uv run python scripts/setup_framework_envs.py

T6 使用父仓库已经验证的 OSIS-AI/OpenCode 环境。各框架版本由 pyproject.toml 与 uv.lock 固定。

## 3. 创建统一技能快照

正式比较不直接挂载父仓库原始模板树。先创建本地、被忽略的快照；构建器排除 templates、tests、answers 和 ground_truth 等高风险目录：

    uv run python scripts/create_skill_snapshot.py --parent-repo PATH_TO_PARENT

六个架构必须使用同一个快照路径和 manifest 中相同的 SHA-256。

## 4. 准备 OSIS scratch 工程

准备一个只供本次实验使用的 OSIS 工程目录。Runner 会在每次验算前替换该目录下的 py 树，因此不要指向人工项目或生产项目。

同时提供 OSIS-AI 使用的 Python 可执行文件。该解释器需要 pyosis，并能执行候选 py/prep/main.py。

## 5. 协议检查

只读列出远端新协议识别出的 seeded 样本：

    uv run python scripts/run_dataset.py \
      --parent-repo PATH_TO_PARENT \
      --architecture T2 \
      --skills-dir tmp/check-repair-skill-snapshot \
      --dry-run

Runner 只选择 status=seeded 的记录。公开任务对象与模型输入中不包含 seed、登记 NG、种错做法或 seeded 路径。

## 6. 单架构正式运行

    uv run python scripts/run_dataset.py \
      --parent-repo PATH_TO_PARENT \
      --architecture T2 \
      --skills-dir tmp/check-repair-skill-snapshot \
      --osis-project PATH_TO_DEDICATED_OSIS_PROJECT \
      --osis-model-python PATH_TO_OSIS_PYTHON \
      --model MODEL_ID \
      --variant high \
      --label formal-v1 \
      --seed 0 \
      --resume

设置 OSIS_MODEL_API_KEY 和 OSIS_MODEL_BASE_URL，密钥只通过进程环境传递。

## 7. 六架构 campaign

    uv run python scripts/run_campaign.py \
      --parent-repo PATH_TO_PARENT \
      --architectures T1 T2 T3 T4 T5 T6 \
      --skills-dir tmp/check-repair-skill-snapshot \
      --osis-project PATH_TO_DEDICATED_OSIS_PROJECT \
      --osis-model-python PATH_TO_OSIS_PYTHON \
      --model MODEL_ID \
      --label formal-v1 \
      --seed 0 \
      --jobs 2 \
      --resume

T1–T5 可以按 jobs 并发调度；T6 始终进入独立串行尾队列，避免共享 OSIS 与 OpenCode 状态冲突。

## 8. 每条 run 的可审计信息

Ignored run 目录包含公开 input、generation、evaluation、manifest 和私有 staging。Manifest 记录协议、父仓库 commit、框架版本、模型、variant、seed、预算、技能哈希、候选前后文件哈希、模型调用数与工具调用数，不记录绝对路径或密钥。

进场前实际 NG 必须与父仓库登记集合完全一致；否则以 SEEDED_NG_MISMATCH 终止且不调用模型。验算结果为空、NOFILE 或 NOHEADER 时同样 fail closed。
