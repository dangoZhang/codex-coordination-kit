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
        guard let snapshot else { return "CoordX" }
        return "B\(snapshot.totals.blocked) W\(snapshot.totals.inProgress)"
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
        let title = seed == nil ? "Register Thread" : "Edit Thread"
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

    func openCollaborationGuide(for thread: Snapshot.ThreadItem) {
        let view = CollaborationGuideWindow(store: self, thread: thread, entry: registryEntry(for: thread))
        if let controller = guideWindowController {
            controller.update(title: "Collaboration Guide", rootView: AnyView(view))
            controller.present()
            return
        }
        let controller = HostedWindowController(
            title: "Collaboration Guide",
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
        copyFeedback = "Copied prompt for \(entry.name)"
    }

    func buildStarterPrompt(for entry: ThreadRegistryEntry) -> String {
        let rootPath = coordinationRootURL?.path ?? "<coordination-root>"
        let baseBranch = snapshot?.baseBranch ?? "main"
        let startCommand = "bash thread_branch_flow.sh start --thread \(entry.id) --scope <scope>"
        return """
        You are `\(entry.name)` (`\(entry.id)`) and own `\(entry.role)`.

        Before coding:
        1. Read these coordination files in `\(rootPath)`:
           - README.md
           - OWNERSHIP.md
           - THREAD_BRIEFS.md
           - TASK_BOARD.md
           - COMM_LOG.md
           - HANDOFFS.md
           - THREADS.json
        2. Only claim work that stays inside your ownership lane.
        3. Start a fresh branch/worktree from the configured base branch `\(baseBranch)`:
           `\(startCommand)`
        4. Write a kickoff entry in COMM_LOG.md before touching tracked target-repo files.

        While working:
        - Keep TASK_BOARD.md current.
        - Stay on your assigned branch/worktree.
        - Finish with a clear handoff when the branch is ready.

        If thread3 blocks the branch:
        - Read the newest review report in `reviews/`.
        - Read the newest rewrite request in `rewrite_requests/`.
        - Make the smallest safe fix on the same branch.
        - Run focused validation and create a new commit.
        - Do not merge to `\(baseBranch)` until thread3 explicitly allows it.
        """
    }

    private func rebuildStarterPrompts(root: URL) throws {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = [root.appendingPathComponent("scripts/generate_starter_prompts.py").path]
        try process.run()
        process.waitUntilExit()
        if process.terminationStatus != 0 {
            throw NSError(domain: "StarterPrompt", code: 2, userInfo: [NSLocalizedDescriptionKey: "Failed to regenerate THREAD_STARTER_PROMPTS.md"])
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
