# Check-repair comparison repository design

- 日期：2026-09-18
- 任务线：第二条线，验算定位与修复
- 仓库：osis-check-repair-comparison

当前实现以 [框架使用说明.md](../../框架使用说明.md) 为准。本文是初始设计，其中 T6 隔离工程和统一自建工具的描述已经过时。
- 状态：设计规格

## 1. 目标与边界

新仓库提供与第一条建模线相同的六框架对比设施（T1–T6），但把任务契约替换为
check-repair 协议。仓库需要让另一台机器能够重建依赖、运行公开 smoke、接入指定版本的
父仓库和 OSIS 环境后复现实验流程。

真实任务数据和实验产物不属于公开仓库。下列内容全部由运行者在仓库外提供，并通过
显式参数或环境变量接入：

- 父仓库中的 datasets/check_repair 正式样本；
- seed、reason_code、ng_baseline、ng_seeded、how 和模板/来源路径；
- 种错后的 py/ 工程、OSISPost.out 和其他原生 OSIS 文件；
- 模型响应、候选工程、运行日志、汇总结果、报告、API 密钥和会话数据库。

Git 中只保留运行器、框架适配器、协议代码、schema、无答案合成 smoke fixture、测试、
锁文件和复现文档。任何真实数据或运行产物进入 tracked 文件都属于发布错误。

## 2. 设计选择

采用独立的干净仓库，而不是复制整份建模线或把第二条线放入建模仓库。第一条线中
已经验证的六框架适配、技能挂载、环境隔离、manifest、工具错误策略和 T6 隔离启动逻辑
按接口提取并复用；建模专用的项目布局、桥型 conformance 评分和旧 TaskSpec 不进入
第二条线。

建议的公开目录：

    common/                  共用路径、技能、框架协议、manifest、边界门禁
    baselines/t1_direct/    T1 一次生成
    baselines/t2_langgraph/ T2 ReAct
    baselines/t3_smolagents/ T3 CodeAct
    baselines/t4_openhands/ T4 CodeAct
    baselines/t5_crewai/    T5 角色编排
    baselines/t6_osisai/    T6 原生 OSIS-AI
    check_repair/            任务 schema、外部数据读取、NG 验算和评分
    scripts/                 单条/批量运行、环境搭建、复现导出、公开边界审计
    tasks/schema/            公开 schema 与无答案合成 smoke fixture
    tests/                   不依赖真实父仓库、网关或 OSIS 的协议测试
    docs/                    复现、环境、数据边界和六框架说明
    configs/                 仅提交 example；local 配置被忽略

## 3. 运行协议

### 3.1 输入净化

CheckRepairTaskSpec 是唯一进入框架层的任务对象，字段为：

- task_id
- bridge_type
- difficulty
- natural_language_prompt
- protocol_version
- total_timeout_s
- metadata（不含答案和种错信息）

外部数据读取器可以保留完整记录供可信驱动使用，但在写入
input.json、adapter_request.json、系统提示词或 T6 hand-off 之前必须调用净化函数。
净化后的序列化内容不得包含 seed、reason_code、ng_、how、答案模板路径或原始
.agents/skills 路径。

### 3.2 单条 run

1. 驱动从外部父仓库读取一条 seeded 记录，解析成净化任务和私有参考记录。
2. 在 ignored 的 runs/<run-id>/private/seeded_project 创建临时工程。可信 verifier
   使用新父协议的 ngutil 对种错模型验算；实际 NG 集合必须与登记值完全相同，否则
   run 失败且不调用模型。
3. SkillAdapter 为六个架构生成同一只读、无答案技能快照和哈希。所有写操作限制在
   本 run 的候选 py/树，路径越界立即返回可恢复的 TOOL_ERROR 或终止 run。
4. T1–T6 按各自框架生成修复候选。生成层不得调用正式评分器、读取私有参考文件或
   访问其他 run。
5. Candidate gate 检查修改路径、文件类型、候选是否存在以及是否保留必要工程入口；
   记录 before/after 文件哈希和 diff 摘要，但不把完整候选提交到 Git。
6. Verifier 清理旧 Check/*.lcc 和临时验算文本，按优先级使用样本外置的
   OSISPost.out + CheckSolve；没有 post 文件时使用 CombinationAndCheck。
   require_complete 必须看到每个验算项的完整状态，NOFILE、NOHEADER 或空结果都
   是失败。
7. Scorer 只在可信驱动侧读取 hidden seed 和 ng_seeded：
   - 从模型最终输出中取最后一个 localizations JSON；
   - 最后一个 reason_code 等于 hidden seed.reason_code 时定位命中；
   - 修复通过条件为目标验算项不在 ng_after 且 ng_after 是 ng_seeded 的子集。
8. Run 写入 ignored 目录的 evaluation.json、manifest.json、阶段轨迹和审计信息。
   汇总脚本只接受显式的 runs 根目录，不能扫描源码树中的任意 JSON 作为结果。

### 3.3 六框架公平性

六个架构共享同一题面、模型、温度/variant、token 和总时限、技能快照、候选写入合同
和 verifier/scorer。mounting_mode 只描述框架暴露技能的方式，不能改变内容。

- T1 为一次请求；不提供交互式工具。
- T2–T5 使用第一条线已锁定的框架版本和工具错误策略，工具只能读公开技能或读写
  当前候选。
- T6 在隔离 OpenCode 项目中运行，挂载同一快照和原生 AGENTS.md；T6 进程与 OSIS
  验算过程串行化，禁止通过祖先目录发现父仓库原始技能树。
- 所有架构的正式验算和评分由统一 runner 完成，框架自身不能把内部检查结果当作正式
  ng_after。

## 4. 发布防护

.gitignore 覆盖虚拟环境、runs/reports/tmp、候选工程、data/、datasets/、
seeded/、private/、模型响应、日志、数据库、OSISPost.out、*.lcc 以及
OSIS 生成的目录。configs/parent_repo.local.txt 只记录本机路径，永不提交。

scripts/audit_public_boundary.py 在发布前检查：

- tracked 文件不含正式样本字段和值（包括 hidden NG、seed.how 和答案路径）；
- tracked 文件不含运行结果目录、原生输出、API key 或机器绝对路径；
- schema/smoke fixture 不含真实模板名、真实原因做法或评分答案；
- Git 状态中的新增文件都落在允许的公开目录。

审计失败返回非零状态，并打印相对路径和命中规则；不会自动删除文件。

## 5. 复现与环境

公开仓库提交 pyproject.toml、uv.lock、.python-version 和环境说明。复现者：

1. 安装 uv，执行 uv sync --python 3.13；
2. 运行框架环境脚本创建 T1–T5 隔离环境；
3. 在外部父仓库按文档创建其 Python/OSIS 环境；
4. 设置 OSIS_PARENT_REPO 或传 --parent-repo，并准备模型网关密钥；
5. 运行公开合成 smoke（不需要真实父数据）；
6. 另行提供正式数据目录后运行单条或批量 check-repair 实验。

README 和 ENVIRONMENT 明确区分“代码/环境/协议可复现”和“历史模型结果不随仓库发布”。
所有结果默认写入 runs/，不会污染源码树的 tracked 文件。

## 6. 错误处理和可审计性

以下情况必须 fail closed：外部 seeded NG 与登记值不一致、候选写越界、技能快照包含
test/answer 信息、验算结果不完整、目标项或新增 NG 解析不确定、父仓库协议版本不匹配。
错误写入结构化 failure code，且 run 不进入正式汇总。

每个 run 的 manifest 固化协议版本、父仓库 commit、框架版本、模型/variant、技能哈希、
随机种子、预算、阶段状态和工件哈希。绝对路径和密钥只存在于本机日志或进程环境，不写
manifest。

## 7. 测试范围

公开测试不依赖外部父仓库、真实 OSIS 或网关，覆盖：

- schema 校验和模型输入净化；
- prompt/JSON 序列化泄漏门禁；
- 候选路径与 diff 门禁；
- seeded NG 完整性校验；
- OSISPost 优先与 CombinationAndCheck fallback；
- require_complete 的空结果、NOFILE、NOHEADER 拒绝；
- 最后一个 JSON 定位、<think> 清理和解析失败计零；
- 目标项消失与新增 NG 集合规则；
- 六框架适配器的统一请求合同、manifest 和运行目录隔离；
- 公开边界审计和复现工作区导出。

真实父仓库专测和真实 OSIS 运行属于环境验证，不作为公开 CI 的必需步骤。
