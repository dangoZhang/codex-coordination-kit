# Codex Coordination Kit

[English README](README.md)

Codex Coordination Kit 用来把一个普通 git 仓库改造成多线程 Codex 协作工作流，包含：

- 独立的协作控制面仓库
- 任务板、通信日志、交接记录
- branch / worktree 规则约束
- 基于 hook 的自动建分支
- 基于 hook 的 Codex 自动 review gate
- 可供看板或机器人消费的状态导出 JSON

这个项目来自一个真实私有协作仓的开源化整理版。仓库路径等本机信息已经从代码里解耦，改成了本地 `gitignore` 的配置文件加 bootstrap 脚本。

## 预览图

真实 macOS StatusBoard 预览窗口截图，使用的是脱敏样例数据：

![已脱敏的 board 预览图](docs/images/board-preview.png)

## 仓库里有什么

- `THREADS.json`：Codex 线程注册表
- `TASK_BOARD.md`：任务看板
- `COMM_LOG.md`：kickoff / blocker / update 日志
- `HANDOFFS.md`：正式交接与 merge gate 记录
- `thread_branch_flow.sh`：创建、审计、合并 branch/worktree
- `install_hooks.sh`：给两个仓库安装 hooks
- `scripts/auto_branch_claim.py`：任务进入 `IN_PROGRESS` 后自动建 worktree
- `scripts/auto_review_gate.py`：在线程分支提交后调用 `codex exec` 做自动 review
- `scripts/export_status.py`：导出状态 JSON，供看板或其它工具使用
- `tools/StatusBoard/`：原生 macOS 菜单栏状态看板
- `rewrite_requests/`：review 被阻塞后生成的重写召回单，默认不纳入版本控制

## 仓库模型

这个仓库是控制面，业务仓库保持独立。

控制面负责规则、日志和自动化；业务仓库负责真正被跟踪的代码。各线程在目标仓库的独立 worktree 中工作，并从基线分支创建自己的线程分支。

## 快速开始

1. 把这个仓库 clone 到你希望放控制面的目录。
2. 用目标仓库路径执行 bootstrap。
3. 安装 hooks。
4. 如果修改了 `THREADS.json`，重新生成 starter prompts。

```bash
cd /path/to/codex-coordination-kit
./bootstrap.sh --target-repo /path/to/target-repo
./install_hooks.sh
python3 scripts/generate_starter_prompts.py
python3 scripts/export_status.py
```

bootstrap 会生成 `coordination.config.json`。这个文件被 `gitignore` 忽略，所以不会把你的本机路径提交到公开仓库。

启动原生 macOS 看板：

```bash
tools/StatusBoard/run.sh
```

如果想把菜单栏程序改成普通窗口模式，方便录屏或截图：

```bash
tools/StatusBoard/run.sh --preview-window
```

如果想直接查看仓库自带的脱敏样例数据：

```bash
CODEX_COORDINATION_SNAPSHOT_FILE=tools/StatusBoard/SampleData/sample_status.json \
tools/StatusBoard/run.sh --preview-window
```

看板里显示的是“上一次完整运行实际耗时”，也就是同一线程最近一次 `kickoff` 到后续最新一条日志之间的时长，不是“距离现在过了多久”。线程注册窗口和协作说明窗口都会以独立窗口打开，所以菜单栏弹层收起后表单也不会丢。

## 标准工作流

1. 在 `TASK_BOARD.md` 中认领任务，并改成 `IN_PROGRESS`。
2. 让控制面仓库 hook 自动建 branch，或者手动执行：

```bash
bash thread_branch_flow.sh start --thread thread11 --scope docs-refresh
```

3. 只在目标仓库生成出来的 worktree 中改代码。
4. 在线程分支上提交。
5. 让目标仓库 hook 触发自动 Codex review。
6. 如果交接记录给出了 `ALLOW_MERGE_TO_BASE`，就手动合并，或者在本地配置里开启 `auto_finish_on_approve`。

审计当前分支状态：

```bash
bash thread_branch_flow.sh audit
```

拿到通过的 review handoff 之后合并：

```bash
bash thread_branch_flow.sh finish \
  --branch codex/thread11-docs-refresh \
  --review-ref H-T3-THREAD11-AUTO-20260314123456 \
  --cleanup-source
```

## Hook 行为

`install_hooks.sh` 会在两个仓库里安装 `post-commit` hook：

- 控制面仓库 `post-commit`：扫描 `TASK_BOARD.md`，为 `auto_branch: true` 且已进入 `IN_PROGRESS` 的线程自动创建 worktree
- 目标仓库 `post-commit`：对当前线程分支执行 `codex exec --output-schema`，并把结果写入 `reviews/`、`HANDOFFS.md`、`COMM_LOG.md`
- 如果 review 返回 `BLOCK_MERGE_TO_BASE`，工具会在 `rewrite_requests/` 下生成重写召回单；若开启配置，还会自动重新调用申请者线程继续修复
- review hook 会在 `runtime/` 下维护按分支划分的锁，避免连续提交时并发跑出多个重叠 review；如果 review 期间同一分支又有新 commit，它会自动追到该分支最新的 commit 再继续审

如果已有 `post-commit` hook，安装器会先把原文件挪到 `post-commit.pre-codex-coordination`，然后串起来继续执行。

## 这个仓库需要单独登录 Codex 吗

这个工具包本身不会附带账号，也不会替你登录。

- 如果运行 hook 的那台机器上，`codex exec` 本来就已经可用，那么这个仓库不需要再额外登录一次。
- 如果那台机器上的 Codex CLI 还没有登录，自动 review hook 就无法执行 Codex review，直到你先把本地 CLI 登录好。
- `coordination.config.json` 只应该放本地路径和运行参数，不应该放 token。

## 隐私说明

- 仓库默认不会跟踪任何本机路径。
- bootstrap 产生的本机配置写在被忽略的 `coordination.config.json` 中。
- README 里的预览图来自真实 SwiftUI StatusBoard 程序，但数据是脱敏样例，不含账号信息。
- 如果你要公开发布自己的 fork，建议不要使用个人邮箱作为 git 提交身份，至少应使用 GitHub noreply 地址或独立 bot 身份。

## 配置项

受版本控制的模板文件：`coordination.config.example.json`

本地运行配置：`coordination.config.json`

字段说明：

- `target_repo`：目标业务仓库绝对路径
- `base_branch`：创建 worktree 和 merge back 的基线分支，通常是 `main` 或 `master`
- `worktree_root`：生成 worktree 的绝对路径
- `codex_command`：调用 Codex 的命令前缀，例如 `["codex"]`
- `codex_exec_args`：插入到 review 调用里的额外参数，例如 model 参数
- `auto_finish_on_approve`：review 通过后是否自动执行 `finish`
- `auto_rewrite_on_block`：review 被阻塞后，是否自动在当前 worktree 重新调用申请者线程修复
- `max_auto_rewrite_attempts`：同一线程分支上的自动重写最大尝试次数，用来防止死循环
- `review_timeout_seconds`：单次自动 review 的超时时间；超时后 hook 会记录 blocker 并退出

## Git 说明

- 最好把这个控制面仓库与目标业务仓库分开存放。
- 如果 `worktree_root` 在目标仓库内部，bootstrap 会自动把它写进目标仓库的 `.gitignore`。
- 如果控制面仓库本身嵌套在目标仓库里，bootstrap 也会自动把控制面目录写进目标仓库的 `.gitignore`。
- 这个项目不强依赖 `master`，基线分支是可配置的。

## 发布

这个仓库可以直接作为公开模板仓或普通公开仓使用。被跟踪的只有通用默认值，所有机器相关配置都留在被忽略的本地配置文件中。
