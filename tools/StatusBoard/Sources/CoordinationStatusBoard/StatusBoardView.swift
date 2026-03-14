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
            Text("CodeX Thread Board")
                .font(.system(size: 16, weight: .semibold))
            if let snapshot = store.snapshot {
                Text("Repo: \(snapshot.repo.currentBranch)\(snapshot.repo.dirty ? " · dirty" : "")")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                HStack(spacing: 8) {
                    Pill(label: "Blocked", value: snapshot.totals.blocked, color: .red)
                    Pill(label: "In Progress", value: snapshot.totals.inProgress, color: .blue)
                    Pill(label: "Todo", value: snapshot.totals.todo, color: .orange)
                    Pill(label: "Done", value: snapshot.totals.done, color: .green)
                }
                if !snapshot.repo.legacyLocalBranches.isEmpty {
                    Text("Legacy branches: \(snapshot.repo.legacyLocalBranches.joined(separator: ", "))")
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
            Button("Refresh") { store.reload() }
            Button("Register Thread") { store.openThreadRegistry() }
            Button("Task Board") { store.openTaskBoard() }
            Button("Comm Log") { store.openCommLog() }
            Button("Coord Repo") { store.openCoordinationRoot() }
            Button("Target Repo") { store.openTargetRepo() }
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
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(thread.displayName)
                    .font(.system(size: 13, weight: .semibold))
                Spacer()
                Text(thread.task?.status ?? "IDLE")
                    .font(.system(size: 10, weight: .semibold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(statusColor.opacity(0.14), in: Capsule())
                    .foregroundStyle(statusColor)
            }

            Text("\(thread.thread) · Slot \(thread.slot) · \(thread.autoBranch ? "Auto branch" : "Manual branch")")
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
                Text("Latest log: [\(log.timestamp)] \(prettyLogType(log.type)) · \(log.message)")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(3)
            }

            let locals = thread.branches.local.map(\.name).joined(separator: ", ")
            Text(locals.isEmpty ? "Local branches: none" : "Local branches: \(locals)")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .lineLimit(2)

            HStack {
                Button("Guide") { store.openCollaborationGuide(for: thread) }
                Button("Edit") { store.openThreadRegistry(seed: entry) }
                Button("Copy Prompt") { store.copyStarterPrompt(for: entry) }
            }
            .buttonStyle(.bordered)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    private var taskSummary: String {
        guard let task = thread.task else {
            return "No task claimed yet. Register the thread or claim a task in TASK_BOARD.md."
        }
        return "Current task: \(task.id) · \(task.title)"
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
        return "Last run duration: \(formatDuration(invocation.elapsedSeconds)) · ended with \(prettyLogType(invocation.endType))"
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
        value
            .replacingOccurrences(of: "_", with: " ")
            .capitalized
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
            Text(seed == nil ? "Register Thread" : "Edit Thread")
                .font(.system(size: 18, weight: .semibold))

            Text("Use this window for thread registration or role updates. It stays open independently from the menu bar popover.")
                .font(.system(size: 12))
                .foregroundStyle(.secondary)

            Form {
                TextField("thread id", text: $threadId)
                TextField("slot", text: $slot)
                TextField("display name", text: $displayName)
                TextField("role", text: $role, axis: .vertical)
                Toggle("Auto create branch on task claim", isOn: $autoBranch)
            }
            .formStyle(.grouped)

            if let errorMessage {
                Text(errorMessage)
                    .font(.system(size: 12))
                    .foregroundStyle(.red)
            }

            HStack {
                Button("Copy Prompt") {
                    do {
                        let entry = try makeEntry()
                        store.copyStarterPrompt(for: entry)
                    } catch {
                        errorMessage = error.localizedDescription
                    }
                }
                Button("Save") {
                    do {
                        let entry = try makeEntry()
                        try store.saveThread(entry: entry, originalId: seed?.id)
                        store.closeThreadRegistry()
                    } catch {
                        errorMessage = error.localizedDescription
                    }
                }
                .keyboardShortcut(.defaultAction)
                Button("Close") { store.closeThreadRegistry() }
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
            throw NSError(domain: "ThreadRegistry", code: 1, userInfo: [NSLocalizedDescriptionKey: "thread id must look like thread8"])
        }
        guard !trimmedSlot.isEmpty, !trimmedName.isEmpty, !trimmedRole.isEmpty else {
            throw NSError(domain: "ThreadRegistry", code: 2, userInfo: [NSLocalizedDescriptionKey: "slot, name, and role are required"])
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
                Text("\(entry.name) Collaboration Guide")
                    .font(.system(size: 20, weight: .semibold))

                Text("\(entry.id) · Slot \(entry.slot) · \(entry.autoBranch ? "Auto branch enabled" : "Manual branch flow")")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)

                guideSection(
                    title: "What This Thread Owns",
                    body: "\(entry.name) handles \(entry.role). Do not pick up work outside that boundary."
                )

                guideSection(
                    title: "Current Task",
                    body: currentTaskText
                )

                guideSection(
                    title: "What To Do Next",
                    body: nextStepText
                )

                VStack(alignment: .leading, spacing: 8) {
                    Text("Most Common Command")
                        .font(.system(size: 14, weight: .semibold))
                    Text("bash thread_branch_flow.sh start --thread \(entry.id) --scope <scope>")
                        .font(.system(size: 12, design: .monospaced))
                        .textSelection(.enabled)
                        .padding(12)
                        .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                }

                guideSection(
                    title: "If Thread3 Blocks You",
                    body: """
                    Stay on the same branch. Read the newest review JSON in reviews/ and the newest note in rewrite_requests/.
                    Make the smallest safe fix, run focused validation, and create a new commit so thread3 can review again.
                    """
                )

                HStack {
                    Button("Open Task Board") { store.openTaskBoard() }
                    Button("Open Comm Log") { store.openCommLog() }
                }
                .buttonStyle(.bordered)

                VStack(alignment: .leading, spacing: 10) {
                    Text("Copyable Prompt")
                        .font(.system(size: 14, weight: .semibold))
                    Text(store.buildStarterPrompt(for: entry))
                        .font(.system(size: 12, design: .monospaced))
                        .textSelection(.enabled)
                        .padding(12)
                        .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                    Button("Copy Prompt") {
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
            return "No task is assigned right now. Claim one in TASK_BOARD.md before you start editing files."
        }

        let statusText: String
        switch task.status {
        case "BLOCKED":
            statusText = "blocked"
        case "IN_PROGRESS":
            statusText = "currently in progress"
        case "DONE":
            statusText = "already marked done"
        default:
            statusText = "ready to start"
        }

        return "Task \(task.id) is \(statusText): \(task.title)"
    }

    private var nextStepText: String {
        let branchGuidance = entry.autoBranch
            ? "After you move the task to IN_PROGRESS, the hook can prepare the branch automatically. If not, run the start command yourself."
            : "This thread does not auto-create branches. Use the start command yourself when you are ready to work."

        if thread.task == nil {
            return """
            1. Pick a task in TASK_BOARD.md that matches \(entry.role).
            2. Mark it IN_PROGRESS.
            3. \(branchGuidance)
            4. Write a kickoff line in COMM_LOG.md before editing tracked files.
            """
        }

        return """
        1. Confirm the task still belongs to \(entry.role).
        2. \(branchGuidance)
        3. Stay inside the thread worktree, keep TASK_BOARD.md current, and finish with a handoff.
        4. If review blocks the branch, fix it on the same branch and resubmit.
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
