import AppKit
import Foundation
import SwiftUI

private final class HostedWindowController: NSWindowController {
    init(title: String, size: NSSize, rootView: AnyView) {
        let hostingController = NSHostingController(rootView: rootView)
        let window = NSWindow(contentViewController: hostingController)
        window.title = title
        window.setContentSize(size)
        window.styleMask = [.titled, .closable, .miniaturizable, .resizable]
        window.isReleasedWhenClosed = false
        window.hidesOnDeactivate = false
        window.collectionBehavior = [.moveToActiveSpace, .fullScreenAuxiliary]
        super.init(window: window)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    func update(title: String, rootView: AnyView) {
        window?.title = title
        if let hostingController = window?.contentViewController as? NSHostingController<AnyView> {
            hostingController.rootView = rootView
        } else {
            window?.contentViewController = NSHostingController(rootView: rootView)
        }
    }

    func present() {
        showWindow(nil)
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}

@MainActor
final class StatusBoardStore: ObservableObject {
    @Published private(set) var snapshot: Snapshot?
    @Published private(set) var errorMessage: String?
    @Published private(set) var copyFeedback: String?

    private let loader = SnapshotLoader()
    private var registryWindowController: HostedWindowController?
    private var guideWindowController: HostedWindowController?

    init() {
        reload()
        Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.reload()
            }
        }
    }

    func reload() {
        do {
            snapshot = try loader.load()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    var menuBarTitle: String {
        guard let snapshot else { return "协作看板" }
        return "阻\(snapshot.totals.blocked) 进\(snapshot.totals.inProgress)"
    }

    var coordinationRootURL: URL? {
        guard let root = snapshot?.coordinationRoot else { return nil }
        return URL(fileURLWithPath: root, isDirectory: true)
    }

    func openCoordinationRoot() {
        guard let url = coordinationRootURL else { return }
        NSWorkspace.shared.open(url)
    }

    func openTargetRepo() {
        guard let root = snapshot?.targetRepoRoot else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: root, isDirectory: true))
    }

    func openTaskBoard() {
        guard let root = coordinationRootURL else { return }
        NSWorkspace.shared.open(root.appendingPathComponent("TASK_BOARD.md"))
    }

    func openCommLog() {
        guard let root = coordinationRootURL else { return }
        NSWorkspace.shared.open(root.appendingPathComponent("COMM_LOG.md"))
    }

    func quitApplication() {
        NSApp.terminate(nil)
    }

    func loadThreadRegistry() throws -> [ThreadRegistryEntry] {
        guard let root = coordinationRootURL else {
            throw CocoaError(.fileNoSuchFile)
        }
        let data = try Data(contentsOf: root.appendingPathComponent("THREADS.json"))
        return try JSONDecoder().decode([ThreadRegistryEntry].self, from: data)
    }

    func saveThread(entry: ThreadRegistryEntry, originalId: String?) throws {
        guard let root = coordinationRootURL else {
            throw CocoaError(.fileNoSuchFile)
        }

        var entries = try loadThreadRegistry()
        if let originalId, let index = entries.firstIndex(where: { $0.id == originalId }) {
            entries[index] = entry
        } else {
            entries.append(entry)
        }

        entries.sort {
            if $0.slot == $1.slot {
                return $0.id < $1.id
            }
            return $0.slot < $1.slot
        }

        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        try encoder.encode(entries).write(to: root.appendingPathComponent("THREADS.json"), options: .atomic)
        try rebuildStarterPrompts(root: root)
        appendCommLogLine(
            "[thread0] [type: update] Updated thread registry for `\(entry.name)` / `\(entry.id)` via StatusBoard; role=`\(entry.role)`, auto_branch=\(entry.autoBranch ? "true" : "false").",
            root: root
        )
        reload()
    }

    func openThreadRegistry(seed: ThreadRegistryEntry? = nil) {
        let title = seed == nil ? "注册线程" : "编辑线程"
        let view = ThreadRegistryWindow(store: self, seed: seed)
        if let controller = registryWindowController {
            controller.update(title: title, rootView: AnyView(view))
            controller.present()
            return
        }
        let controller = HostedWindowController(
            title: title,
            size: NSSize(width: 460, height: 420),
            rootView: AnyView(view)
        )
        registryWindowController = controller
        controller.present()
    }

    func closeThreadRegistry() {
        registryWindowController?.close()
    }

    func registryEntry(for thread: Snapshot.ThreadItem) -> ThreadRegistryEntry {
        ThreadRegistryEntry(
            id: thread.thread,
            slot: thread.slot,
            name: thread.displayName,
            role: thread.role,
            autoBranch: thread.autoBranch
        )
    }

    func threadItem(for threadID: String) -> Snapshot.ThreadItem? {
        snapshot?.threads.first(where: { $0.thread == threadID })
    }

    func persistentBranch(for threadID: String) -> String? {
        threadItem(for: threadID)?.branches.persistentBranch
    }

    func openCollaborationGuide(for thread: Snapshot.ThreadItem) {
        let view = CollaborationGuideWindow(store: self, thread: thread, entry: registryEntry(for: thread))
        if let controller = guideWindowController {
            controller.update(title: "协作说明", rootView: AnyView(view))
            controller.present()
            return
        }
        let controller = HostedWindowController(
            title: "协作说明",
            size: NSSize(width: 620, height: 640),
            rootView: AnyView(view)
        )
        guideWindowController = controller
        controller.present()
    }

    func copyStarterPrompt(for entry: ThreadRegistryEntry) {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(buildStarterPrompt(for: entry), forType: .string)
        copyFeedback = "已复制 \(entry.name) 的启动指令"
    }

    func buildStarterPrompt(for entry: ThreadRegistryEntry) -> String {
        let rootPath = coordinationRootURL?.path ?? "<coordination-root>"
        let baseBranch = snapshot?.baseBranch ?? "main"
        let repoConfigNote = "2. 在目标仓库中优先阅读 `AGENTS.md`、`.codex/AGENTS.md`、`.agent/coordination.json`。"
        let persistentBranch = persistentBranch(for: entry.id)
        let startCommand = persistentBranch == nil
            ? "bash thread_branch_flow.sh start --thread \(entry.id) --scope <scope> --task <TASK_ID> --note \"kickoff note\""
            : "bash thread_branch_flow.sh start --thread \(entry.id) --task <TASK_ID> --note \"kickoff note\""
        let branchInstruction = persistentBranch == nil
            ? "3. 从配置的基线分支 `\(baseBranch)` 创建新的 scoped branch/worktree："
            : "3. 复用配置好的持久分支 `\(persistentBranch!)`，并在每次工作前把它同步到 `\(baseBranch)`："
        let workingLine = persistentBranch == nil
            ? "- 始终在分配给你的 scoped branch/worktree 中工作。"
            : "- 始终在分配给你的持久分支/worktree 中工作。"
        return """
        你现在是 `\(entry.name)`（`\(entry.id)`），负责 `\(entry.role)`。

        开始编码前：
        1. 阅读 `\(rootPath)` 下这些协作文件：
           - README.md
           - OWNERSHIP.md
           - THREAD_BRIEFS.md
           - TASK_BOARD.md
           - COMM_LOG.md
           - HANDOFFS.md
           - THREADS.json
        \(repoConfigNote)
        3. 只认领属于你职责范围内的工作。
        4. \(branchInstruction.dropFirst(3))
           `\(startCommand)`
        5. 不要提交代码，直到 TASK_BOARD.md 已经把任务标成 IN_PROGRESS，并且 COMM_LOG.md 里有带任务 ID 的 kickoff。

        工作过程中：
        - 保持 TASK_BOARD.md 和 COMM_LOG.md 状态最新。
        \(workingLine)
        - 分支准备好后，写清晰的 handoff。

        如果 thread3 阻塞了分支：
        - 阅读 `reviews/` 里的最新 review 报告。
        - 阅读 `rewrite_requests/` 里的最新重写请求。
        - 在同一条分支上做最小必要修复。
        - 运行有针对性的验证并提交新的 commit。
        - 在 thread3 明确放行前，不要合并到 `\(baseBranch)`。
        """
    }

    private func rebuildStarterPrompts(root: URL) throws {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = [root.appendingPathComponent("scripts/generate_starter_prompts.py").path]
        try process.run()
        process.waitUntilExit()
        if process.terminationStatus != 0 {
            throw NSError(domain: "StarterPrompt", code: 2, userInfo: [NSLocalizedDescriptionKey: "重新生成 THREAD_STARTER_PROMPTS.md 失败"])
        }
    }

    private func appendCommLogLine(_ message: String, root: URL) {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd HH:mm"
        let line = "[\(formatter.string(from: Date()))] \(message)\n"
        let url = root.appendingPathComponent("COMM_LOG.md")
        guard let handle = try? FileHandle(forWritingTo: url) else { return }
        defer { try? handle.close() }
        _ = try? handle.seekToEnd()
        if let data = line.data(using: .utf8) {
            try? handle.write(contentsOf: data)
        }
    }
}
