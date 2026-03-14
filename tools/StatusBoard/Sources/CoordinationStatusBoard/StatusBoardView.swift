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
                        ThreadCard(thread: thread)
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
            }
        }
    }

    private var footer: some View {
        HStack {
            Button("Refresh") { store.reload() }
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
    let thread: Snapshot.ThreadItem

    var body: some View {
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

            Text(thread.task.map { "\($0.id) · \($0.title)" } ?? "No registered task")
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
                Text("[\(log.timestamp)] \(log.type) · \(log.message)")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(3)
            }

            let locals = thread.branches.local.map(\.name).joined(separator: ", ")
            Text(locals.isEmpty ? "Local branches: none" : "Local branches: \(locals)")
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.35), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
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
        guard let runtimeStart = thread.runtimeStart else { return nil }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd HH:mm"
        guard let startedAt = formatter.date(from: runtimeStart.timestamp) else {
            return "Started at \(runtimeStart.timestamp)"
        }
        let elapsed = max(Int(Date().timeIntervalSince(startedAt)), 0)
        let hours = elapsed / 3600
        let minutes = (elapsed % 3600) / 60
        return "Running for \(hours)h \(minutes)m"
    }
}
