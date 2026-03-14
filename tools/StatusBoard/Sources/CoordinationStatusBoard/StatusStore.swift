import AppKit
import Foundation
import SwiftUI

@MainActor
final class StatusBoardStore: ObservableObject {
    @Published private(set) var snapshot: Snapshot?
    @Published private(set) var errorMessage: String?

    private let loader = SnapshotLoader()

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
}
