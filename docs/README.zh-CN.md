<p align="right">
  <a href="../README.md">English</a> | <strong>简体中文</strong>
</p>

# Codex Coordination

Codex Coordination 是一套开源的多线程 Codex 协作控制面。

它把普通 git 仓库接成一套可治理的协作流程，包含：

- 独立的协作仓库
- 明确的线程职责和任务流转
- 分支与 worktree 自动化
- 基于 hook 的 `codex exec` 自动审核
- 通过 `AGENTS.md`、`.codex/AGENTS.md`、`.agent/coordination.json` 下发仓库级规则
- 原生 macOS 状态看板

## 这是什么

这个仓库不是业务代码仓，而是业务仓外围的协作控制层。

控制面仓库负责：

- 线程注册与任务看板
- 通信日志与交接记录
- hook 安装
- review 自动化
- starter prompts
- 看板状态导出

目标仓库负责真实业务代码。生产线程会在目标仓库从基线分支派生出的 worktree 中工作。

## 效果图

真实 StatusBoard 窗口，使用脱敏样例数据：

![StatusBoard 预览图](images/board-preview.png)

## 怎么做的

1. 先把目标仓库注册进控制面。
2. 向目标仓库安装 hooks 和仓库级 Codex 规则。
3. 在线程任务板里认领任务。
4. 在线程对应的分支和 worktree 中开发。
5. 在目标仓库提交。
6. 让 hooks 自动触发 Codex review。
7. 只有拿到 `ALLOW_MERGE_TO_BASE` 才允许合并。

默认 demo 自带五个线程：

- `thread0`：产品 / 协调
- `thread1`：后端自动化，默认持久分支 `codex/thread1-mainline`
- `thread2`：board 前端
- `thread3`：review gate
- `thread4`：README / 文档

## 怎么部署

```bash
git clone https://github.com/dangoZhang/codex-coordination-kit.git codex-coordination
cd codex-coordination
./scripts/register_project.sh --target-repo /path/to/target-repo
python3 scripts/generate_starter_prompts.py
./tools/StatusBoard/run.sh
```

注册会自动完成四件事：

- 写入本地 `coordination.config.json`
- 给控制面仓库和目标仓库安装 hooks
- 向目标仓库安装 `AGENTS.md`、`.codex/AGENTS.md`、`.agent/coordination.json`
- 立刻运行 `doctor`，尽早暴露接线问题

常用检查命令：

```bash
./scripts/doctor.sh --require-hooks
python3 scripts/self_test.py
python3 scripts/export_status.py
```

## 常用命令

普通 scoped 线程：

```bash
bash scripts/thread_branch_flow.sh start --thread thread2 --scope board-polish --task T2-BOARD-001 --note "kickoff note"
```

持久 `thread1`：

```bash
bash scripts/thread_branch_flow.sh start --thread thread1 --task T1-BACKEND-001 --note "kickoff note"
```

审核通过后合并：

```bash
bash scripts/thread_branch_flow.sh finish \
  --branch codex/thread2-board-polish \
  --review-ref H-T3-THREAD2-AUTO-20260314123456 \
  --task T2-BOARD-001
```

## 结构

```text
.
├── docs/
│   ├── README.zh-CN.md
│   └── images/
├── schemas/
│   └── review_gate.schema.json
├── scripts/
│   ├── *.py
│   ├── bootstrap.sh
│   ├── doctor.sh
│   ├── install_hooks.sh
│   ├── register_project.sh
│   └── thread_branch_flow.sh
├── templates/
│   └── repo/
├── tools/
│   └── StatusBoard/
├── THREADS.json
├── TASK_BOARD.md
├── COMM_LOG.md
├── HANDOFFS.md
└── THREAD_STARTER_PROMPTS.md
```

关键目录：

- `scripts/`：所有自动化入口统一放在这里
- `docs/`：预览图和多语言文档
- `templates/repo/`：安装到目标仓库的规则模板
- `tools/StatusBoard/`：原生 macOS board
- 根目录协作文件：内置 demo 的控制面状态

## 说明

- 看板显示的是“上次完整运行实际耗时”，不是“多久前运行过”。
- `thread1` 使用持久分支，目的是减少长时间审核时的冲突分叉扩散。
- review 被阻塞时，系统可以生成 rewrite request，并按配置自动重新调用申请者线程。
- 仓库中不会保存任何账号凭据。本机配置只放在被忽略的 `coordination.config.json`。

## 中英文切换

GitHub 仓库 README 目前没有原生语言切换按钮。这里采用的是页顶双语链接，在 GitHub Web 界面中可直接点击切换。GitHub 官方文档可参考 [About READMEs](https://docs.github.com/articles/about-readmes) 和 [Relative links and image paths in markdown files](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)。
