import SwiftUI

struct StatusBoardView: View {
    @ObservedObject var store: StatusBoardStore

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            header
            Divider()
            if let errorMessage = store.errorMessage {
                Text(errorMessage)
                    .foregroundStyle(.red)
                    .font(.system(size: 12))
            }
            ScrollView {
                LazyVStack(spacing: 10) {
                    ForEach(store.snapshot?.threads ?? []) { thread in
                        ThreadCard(store: store, thread: thread)
                    }
                }
            }
            Divider()
            footer
        }
        .padding(14)
        .frame(width: 460, height: 620)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("CodeX 线程看板")
                .font(.system(size: 16, weight: .semibold))
            if let snapshot = store.snapshot {
                Text("仓库：\(snapshot.repo.currentBranch)\(snapshot.repo.dirty ? " · 有未提交改动" : "")")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                HStack(spacing: 8) {
                    Pill(label: "阻塞", value: snapshot.totals.blocked, color: .red)
                    Pill(label: "进行中", value: snapshot.totals.inProgress, color: .blue)
                    Pill(label: "待办", value: snapshot.totals.todo, color: .orange)
                    Pill(label: "完成", value: snapshot.totals.done, color: .green)
                }
                if !snapshot.repo.legacyLocalBranches.isEmpty {
                    Text("遗留分支：\(snapshot.repo.legacyLocalBranches.joined(separator: ", "))")
                        .font(.system(size: 11))
                        .foregroundStyle(.orange)
                        .lineLimit(2)
                }
                if let feedback = store.copyFeedback {
                    Text(feedback)
                        .font(.system(size: 11))
                        .foregroundStyle(.green)
                }
            }
        }
    }

    private var footer: some View {
        HStack {
            Button("刷新") { store.reload() }
            Button("注册线程") { store.openThreadRegistry() }
            Button("任务板") { store.openTaskBoard() }
            Button("通信日志") { store.openCommLog() }
            Button("协作仓") { store.openCoordinationRoot() }
            Button("业务仓") { store.openTargetRepo() }
            Spacer(minLength: 0)
            Button("退出") { store.quitApplication() }
        }
        .buttonStyle(.bordered)
    }
}

private struct Pill: View {
    let label: String
    let value: Int
    let color: Color

    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(label)
            Text("\(value)").fontWeight(.semibold)
        }
        .font(.system(size: 11))
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(color.opacity(0.12), in: Capsule())
    }
}

private struct ThreadCard: View {
    @ObservedObject var store: StatusBoardStore
    let thread: Snapshot.ThreadItem

    var body: some View {
        let entry = store.registryEntry(for: thread)
        let persistentBranch = thread.branches.persistentBranch
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(thread.displayName)
                    .font(.system(size: 13, weight: .semibold))
                Spacer()
                Text(localizedStatus(thread.task?.status ?? "IDLE"))
                    .font(.system(size: 10, weight: .semibold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(statusColor.opacity(0.14), in: Capsule())
                    .foregroundStyle(statusColor)
            }

            Text(
                "\(thread.thread) · 槽位 \(thread.slot) · "
                    + (persistentBranch == nil
                        ? (thread.autoBranch ? "按任务自动建分支" : "手动建分支")
                        : "持久分支模式")
            )
                .font(.system(size: 10))
                .foregroundStyle(.secondary)

            Text(taskSummary)
                .font(.system(size: 12))
                .lineLimit(2)

            Text(thread.role)
                .font(.system(size: 11))
                .foregroundStyle(.secondary)

            if let runtimeText = runtimeText {
                Text(runtimeText)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(.blue)
            }

            if let log = thread.lastLog {
                Text("最新日志：[ \(log.timestamp) ] \(prettyLogType(log.type)) · \(log.message)")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(3)
            }

            let locals = thread.branches.local.map(\.name).joined(separator: ", ")
            Text(locals.isEmpty ? "本地分支：无" : "本地分支：\(locals)")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .lineLimit(2)

            HStack {
                Button("协作说明") { store.openCollaborationGuide(for: thread) }
                Button("编辑") { store.openThreadRegistry(seed: entry) }
                Button("复制指令") { store.copyStarterPrompt(for: entry) }
            }
            .buttonStyle(.bordered)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private var taskSummary: String {
        guard let task = thread.task else {
            return "当前还没有认领任务。请先注册线程或在 TASK_BOARD.md 中认领任务。"
        }
        return "当前任务：\(task.id) · \(task.title)"
    }

    private var statusColor: Color {
        switch thread.task?.status {
        case "BLOCKED": return .red
        case "IN_PROGRESS": return .blue
        case "TODO": return .orange
        case "DONE": return .green
        default: return .secondary
        }
    }

    private var runtimeText: String? {
        guard let invocation = thread.lastInvocation else { return nil }
        return "上次运行耗时：\(formatDuration(invocation.elapsedSeconds)) · 结束状态：\(prettyLogType(invocation.endType))"
    }

    private func formatDuration(_ seconds: Int) -> String {
        let hours = seconds / 3600
        let minutes = (seconds % 3600) / 60
        let remainingSeconds = seconds % 60
        if hours > 0 {
            return "\(hours)h \(minutes)m"
        }
        if minutes > 0 {
            return "\(minutes)m \(remainingSeconds)s"
        }
        return "\(remainingSeconds)s"
    }

    private func prettyLogType(_ value: String) -> String {
        switch value {
        case "kickoff":
            return "启动"
        case "update":
            return "更新"
        case "blocker":
            return "阻塞"
        case "handoff":
            return "交接"
        case "allow_merge_to_base":
            return "允许合并"
        case "block_merge_to_base":
            return "阻止合并"
        default:
            return value.replacingOccurrences(of: "_", with: " ")
        }
    }

    private func localizedStatus(_ value: String) -> String {
        switch value {
        case "BLOCKED":
            return "阻塞"
        case "IN_PROGRESS":
            return "进行中"
        case "TODO":
            return "待办"
        case "DONE":
            return "完成"
        case "IDLE":
            return "空闲"
        default:
            return value
        }
    }
}

struct ThreadRegistryWindow: View {
    @ObservedObject var store: StatusBoardStore
    let seed: ThreadRegistryEntry?

    @State private var threadId = ""
    @State private var slot = ""
    @State private var displayName = ""
    @State private var role = ""
    @State private var autoBranch = true
    @State private var errorMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(seed == nil ? "注册线程" : "编辑线程")
                .font(.system(size: 18, weight: .semibold))

            Text("这个窗口用于注册线程或更新职责。它会以独立窗口保持打开，不受菜单栏弹层收起影响。")
                .font(.system(size: 12))
                .foregroundStyle(.secondary)

            Form {
                TextField("线程 ID", text: $threadId)
                TextField("槽位", text: $slot)
                TextField("显示名称", text: $displayName)
                TextField("职责", text: $role, axis: .vertical)
                Toggle("认领任务后自动创建分支", isOn: $autoBranch)
            }
            .formStyle(.grouped)

            if let errorMessage {
                Text(errorMessage)
                    .font(.system(size: 12))
                    .foregroundStyle(.red)
            }

            HStack {
                Button("复制指令") {
                    do {
                        let entry = try makeEntry()
                        store.copyStarterPrompt(for: entry)
                    } catch {
                        errorMessage = error.localizedDescription
                    }
                }
                Button("保存") {
                    do {
                        let entry = try makeEntry()
                        try store.saveThread(entry: entry, originalId: seed?.id)
                        store.closeThreadRegistry()
                    } catch {
                        errorMessage = error.localizedDescription
                    }
                }
                .keyboardShortcut(.defaultAction)
                Button("关闭") { store.closeThreadRegistry() }
            }
        }
        .padding(18)
        .onAppear {
            if let seed {
                threadId = seed.id
                slot = seed.slot
                displayName = seed.name
                role = seed.role
                autoBranch = seed.autoBranch
            }
        }
    }

    private func makeEntry() throws -> ThreadRegistryEntry {
        let trimmedId = threadId.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedSlot = slot.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedName = displayName.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedRole = role.trimmingCharacters(in: .whitespacesAndNewlines)

        guard trimmedId.hasPrefix("thread"),
              Int(trimmedId.dropFirst("thread".count)) != nil else {
            throw NSError(domain: "ThreadRegistry", code: 1, userInfo: [NSLocalizedDescriptionKey: "线程 ID 必须是 thread0 这种格式"])
        }
        guard !trimmedSlot.isEmpty, !trimmedName.isEmpty, !trimmedRole.isEmpty else {
            throw NSError(domain: "ThreadRegistry", code: 2, userInfo: [NSLocalizedDescriptionKey: "槽位、名称和职责都必须填写"])
        }

        return ThreadRegistryEntry(
            id: trimmedId,
            slot: trimmedSlot,
            name: trimmedName,
            role: trimmedRole,
            autoBranch: autoBranch
        )
    }
}

struct CollaborationGuideWindow: View {
    @ObservedObject var store: StatusBoardStore
    let thread: Snapshot.ThreadItem
    let entry: ThreadRegistryEntry

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("\(entry.name) 协作说明")
                    .font(.system(size: 20, weight: .semibold))

                Text("\(entry.id) · 槽位 \(entry.slot) · \(entry.autoBranch ? "已启用自动建分支" : "手动分支流程")")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)

                guideSection(
                    title: "负责范围",
                    body: "\(entry.name) 负责 \(entry.role)。不要认领超出这个边界的工作。"
                )

                guideSection(
                    title: "当前任务",
                    body: currentTaskText
                )

                guideSection(
                    title: "下一步怎么做",
                    body: nextStepText
                )

                VStack(alignment: .leading, spacing: 8) {
                    Text("最常用命令")
                        .font(.system(size: 14, weight: .semibold))
                    Text(
                        thread.branches.persistentBranch == nil
                            ? "bash thread_branch_flow.sh start --thread \(entry.id) --scope <scope> --task <TASK_ID> --note \"kickoff note\""
                            : "bash thread_branch_flow.sh start --thread \(entry.id) --task <TASK_ID> --note \"kickoff note\""
                    )
                        .font(.system(size: 12, design: .monospaced))
                        .textSelection(.enabled)
                        .padding(12)
                        .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                }

                guideSection(
                    title: "如果被 thread3 阻塞",
                    body: """
                    保持在同一条\(thread.branches.persistentBranch == nil ? "" : "持久")分支上。先阅读 reviews/ 里的最新 review JSON，再看 rewrite_requests/ 里的最新重写说明。
                    只做最小必要修复，跑有针对性的验证，然后提交一个新 commit 让 thread3 重新审核。
                    """
                )

                HStack {
                    Button("打开任务板") { store.openTaskBoard() }
                    Button("打开通信日志") { store.openCommLog() }
                }
                .buttonStyle(.bordered)

                VStack(alignment: .leading, spacing: 10) {
                    Text("可复制启动指令")
                        .font(.system(size: 14, weight: .semibold))
                    Text(store.buildStarterPrompt(for: entry))
                        .font(.system(size: 12, design: .monospaced))
                        .textSelection(.enabled)
                        .padding(12)
                        .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                    Button("复制指令") {
                        store.copyStarterPrompt(for: entry)
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
            .padding(18)
        }
    }

    private var currentTaskText: String {
        guard let task = thread.task else {
            return "当前还没有分配任务。开始改文件前，请先在 TASK_BOARD.md 中认领任务。"
        }

        let statusText: String
        switch task.status {
        case "BLOCKED":
            statusText = "已阻塞"
        case "IN_PROGRESS":
            statusText = "进行中"
        case "DONE":
            statusText = "已完成"
        default:
            statusText = "待开始"
        }

        return "任务 \(task.id) 当前\(statusText)：\(task.title)"
    }

    private var nextStepText: String {
        let branchGuidance: String
        if let persistentBranch = thread.branches.persistentBranch {
            branchGuidance = entry.autoBranch
                ? "把任务改成 IN_PROGRESS 后，hook 会自动准备或复用持久分支 `\(persistentBranch)`；如果没有自动处理，就手动运行上面的 start 命令。"
                : "这个线程不会自动建分支。准备开始时，请手动运行上面的 start 命令，先把 `\(persistentBranch)` 和基线同步。"
        } else {
            branchGuidance = entry.autoBranch
                ? "把任务改成 IN_PROGRESS 后，hook 会自动准备新的 scoped 分支；如果没有自动创建，就手动运行上面的 start 命令。"
                : "这个线程不会自动建分支。准备开始时，请手动运行上面的 start 命令创建 scoped 分支。"
        }

        if thread.task == nil {
            return """
            1. 在 TASK_BOARD.md 中挑一个符合 \(entry.role) 职责的任务。
            2. 把它标记成 IN_PROGRESS。
            3. \(branchGuidance)
            4. 在修改受跟踪文件前，用 `thread_branch_flow.sh --task ... --note ...` 或 `coord_task_event.py start ...` 写入 kickoff。
            """
        }

        return """
        1. 先确认这个任务仍然属于 \(entry.role) 的职责范围。
        2. \(branchGuidance)
        3. 全程在该线程分配到的 worktree 中工作，保持 TASK_BOARD.md 状态最新，并在完成时写交接。
        4. 如果 review 阻塞了分支，就在同一条分支上修复后重新提交。
        """
    }

    private func guideSection(title: String, body: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.system(size: 14, weight: .semibold))
            Text(body)
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
        }
    }
}
