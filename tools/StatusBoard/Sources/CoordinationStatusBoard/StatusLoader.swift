import Foundation

enum SnapshotError: LocalizedError {
    case snapshotFileMissing
    case exporterFailed(String)
    case decodeFailed

    var errorDescription: String? {
        switch self {
        case .snapshotFileMissing:
            return "Missing CODEX_COORDINATION_SNAPSHOT_FILE or exporter root."
        case .exporterFailed(let output):
            return "Status export failed: \(output)"
        case .decodeFailed:
            return "Could not decode snapshot JSON."
        }
    }
}

struct SnapshotLoader {
    func load() throws -> Snapshot {
        if let snapshotFile = ProcessInfo.processInfo.environment["CODEX_COORDINATION_SNAPSHOT_FILE"] {
            let data = try Data(contentsOf: URL(fileURLWithPath: snapshotFile))
            let decoder = JSONDecoder()
            guard let snapshot = try? decoder.decode(Snapshot.self, from: data) else {
                throw SnapshotError.decodeFailed
            }
            return snapshot
        }

        let coordinationRoot = ProcessInfo.processInfo.environment["CODEX_COORDINATION_ROOT"]
            ?? URL(fileURLWithPath: #filePath)
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .deletingLastPathComponent()
                .path
        let scriptURL = URL(fileURLWithPath: coordinationRoot).appendingPathComponent("scripts/export_status.py")
        guard FileManager.default.fileExists(atPath: scriptURL.path) else {
            throw SnapshotError.snapshotFileMissing
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = [scriptURL.path]

        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe

        try process.run()
        process.waitUntilExit()

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard process.terminationStatus == 0 else {
            throw SnapshotError.exporterFailed(String(decoding: data, as: UTF8.self))
        }

        let decoder = JSONDecoder()
        guard let snapshot = try? decoder.decode(Snapshot.self, from: data) else {
            throw SnapshotError.decodeFailed
        }
        return snapshot
    }
}
