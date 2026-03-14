import AppKit
import SwiftUI

struct LaunchOptions {
    let dumpSnapshot: Bool
    let previewWindow: Bool

    static func parse(_ arguments: [String]) -> LaunchOptions {
        LaunchOptions(
            dumpSnapshot: arguments.contains("--dump-snapshot"),
            previewWindow: arguments.contains("--preview-window")
        )
    }
}

@main
struct CoordinationStatusBoardLauncher {
    static func main() {
        let options = LaunchOptions.parse(Array(CommandLine.arguments.dropFirst()))
        if options.dumpSnapshot {
            do {
                let snapshot = try SnapshotLoader().load()
                print(snapshot.summaryText)
            } catch {
                fputs("Snapshot load failed: \(error.localizedDescription)\n", stderr)
                exit(1)
            }
            return
        }

        if options.previewWindow {
            StatusBoardPreviewApp.main()
        } else {
            StatusBoardMenuBarApp.main()
        }
    }
}

final class MenuBarAppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
    }
}

final class PreviewAppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}

struct StatusBoardMenuBarApp: App {
    @NSApplicationDelegateAdaptor(MenuBarAppDelegate.self) private var appDelegate
    @StateObject private var store = StatusBoardStore()

    var body: some Scene {
        MenuBarExtra(store.menuBarTitle, systemImage: "list.bullet.rectangle") {
            StatusBoardView(store: store)
        }
        .menuBarExtraStyle(.window)

        Settings {
            EmptyView()
        }
    }
}

struct StatusBoardPreviewApp: App {
    @NSApplicationDelegateAdaptor(PreviewAppDelegate.self) private var appDelegate
    @StateObject private var store = StatusBoardStore()

    var body: some Scene {
        WindowGroup("CodeX Thread Board") {
            StatusBoardView(store: store)
        }
        .defaultSize(width: 470, height: 640)

        Settings {
            EmptyView()
        }
    }
}
