# Codex Coordination

[English README](README.md)

Codex Coordination 用来把普通 git 仓库接成一套多线程 Codex 协作流程，包含独立控制面、自动 review gate，以及原生 macOS 状态看板。

它不是一堆 prompt 模板，而是一套可直接运行的协作基础设施：

- 控制面仓库与业务仓库分离
- 任务板、通信日志、交接记录
- 线程分支与 worktree 自动化
- 基于 hook 的 `codex exec` 自动审核
- 通过 `AGENTS.md`、`.codex/AGENTS.md`、`.agent/coordination.json` 下发仓库级规则
- 状态导出，可供 board、bot 或其它工具消费

## 预览

真实 StatusBoard 窗口，使用脱敏样例数据：

![StatusBoard 预览图](docs/images/board-preview.png)

## 这个项目解决什么问题

Codex 多线程协作常见的失效点通常是：

- 线程职责不清
- 分支持续漂移并产生冲突
- review 很容易被绕过
- 本机路径被误提交
- 仓库自己的规则无法稳定传达给每个线程

这个项目用“控制面仓库 + 目标仓库规则安装”的方式处理这些问题。业务代码仍然留在目标仓库，协作规则、日志、hooks、review 流程则由控制面负责。

## 核心组成

- `THREADS.json`：线程注册表
- `TASK_BOARD.md`：任务队列与归属
- `COMM_LOG.md`：kickoff、阻塞、进度日志
- `HANDOFFS.md`：review 与 merge 交接记录
- `thread_branch_flow.sh`：启动、审计、收尾分支流程
- `register_project.sh`：一键注册已有仓库
- `doctor.sh`：检查配置、hooks、状态导出
- `tools/StatusBoard/`：原生 macOS 看板

## 快速开始

```bash
cd /path/to/codex-coordination
./register_project.sh --target-repo /path/to/target-repo
python3 scripts/generate_starter_prompts.py
tools/StatusBoard/run.sh
```

注册流程会自动完成：

- 写入本地 `coordination.config.json`
- 给控制面仓库和目标仓库安装 hooks
- 向目标仓库安装 `AGENTS.md`、`.codex/AGENTS.md`、`.agent/coordination.json`
- 立即执行 `doctor`，把接线问题直接暴露出来

如果目标仓库当前只有 `origin/main` 或 `origin/master`，bootstrap 也会自动补本地 tracking branch。

## 默认 Demo

仓库自带一个 5 线程 demo，可直接拿来演示或自举：

- `thread0`：产品 / 协调者
- `thread1`：后端自动化
- `thread2`：board 前端
- `thread3`：review gate
- `thread4`：README / 文档

其中 `thread1` 默认使用持久分支：

- `codex/thread1-mainline`

每次新任务开始前，这条分支都会先同步到最新基线分支。其它生产线程仍然按任务使用 scoped 分支，例如 `codex/thread2-board-polish`。

## 标准流程

1. 在 `TASK_BOARD.md` 中认领任务。
2. 启动线程分支，或让 hooks 自动创建。
3. 只在生成出来的目标仓库 worktree 中改代码。
4. 在线程分支提交。
5. 让 hooks 触发 Codex 自动 review。
6. 收到 `ALLOW_MERGE_TO_BASE` 后再合并，或开启 `auto_finish_on_approve` 自动收尾。

普通 scoped 线程示例：

```bash
bash thread_branch_flow.sh start --thread thread2 --scope board-polish --task T2-BOARD-001 --note "kickoff note"
```

持久 `thread1` 示例：

```bash
bash thread_branch_flow.sh start --thread thread1 --task T1-BACKEND-001 --note "kickoff note"
```

review 通过后合并：

```bash
bash thread_branch_flow.sh finish \
  --branch codex/thread2-board-polish \
  --review-ref H-T3-THREAD2-AUTO-20260314123456 \
  --task T2-BOARD-001
```

## Hooks 与 Review Gate

安装后的 hooks 会把协作闭环真正接起来：

- 控制面仓库 `post-commit`：为已认领任务自动创建 worktree
- 目标仓库 `pre-commit`：没有合法 `IN_PROGRESS` 任务和 kickoff 日志时阻止提交
- 目标仓库 `post-commit`：异步执行 `codex exec --output-schema` 自动审核
- 目标仓库 `pre-push`：push 前再次触发审核兜底

如果 review 被阻塞，可以自动生成 rewrite request，并重新调用申请者线程继续修复。review 运行器还会按分支加锁，避免连续提交时启动多个重叠审核。

## 仓库级 Codex 规则

目标仓库会安装三份文件：

- `AGENTS.md`
- `.codex/AGENTS.md`
- `.agent/coordination.json`

这三份文件才是仓库级行为约束的核心入口。它们用来定义职责边界、协作规则和隐私约束，同时不会泄露本机账号状态或本地认证文件。

如果目标仓库已经有自己维护的这些文件，且不属于本项目托管版本，bootstrap 会保留原文件，不会强制覆盖。

## 健康检查

```bash
./doctor.sh --require-hooks
python3 scripts/self_test.py
```

`doctor` 会检查：

- 协作必需文件
- 目标仓库接线状态
- 基线分支可用性
- 仓库级 agent 配置是否存在
- `codex` 可执行文件是否可用
- 状态导出是否正常
- hooks 是否已安装

## StatusBoard 说明

macOS 看板显示的是“上一次完整运行实际耗时”，不是“距离现在过去了多久”。线程注册和协作说明面板会以独立窗口打开，不会因为菜单栏弹层关闭而消失。

## 隐私

- 本机配置只写入被忽略的 `coordination.config.json`
- 仓库本身不携带任何凭据
- `AGENTS.md`、`.codex`、`.agent` 中不会写入账号信息
- 预览图使用的是脱敏样例数据

如果运行 `codex exec` 的机器本来就已经可用 Codex CLI，则不需要为这个项目额外登录。若该机器尚未登录，本地自动 review 在登录前无法运行。
