import SwiftUI
import WidgetKit

// Minimal host app: macOS only shows a widget if it ships inside an app. Open it once so the system registers the widget.
// Launched with `--reload` (by progress.py after each write) it only asks WidgetKit to refresh the widget, then quits without UI.
private let reloadOnly = CommandLine.arguments.contains("--reload")

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationWillFinishLaunching(_ notification: Notification) {
        guard reloadOnly else { return }
        NSApp.setActivationPolicy(.prohibited)
        WidgetCenter.shared.reloadAllTimelines()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { NSApp.terminate(nil) }
    }
}

@main
struct UnitutorApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate

    var body: some Scene {
        WindowGroup {
            VStack(spacing: 8) {
                Text("Unitutor widget installed").font(.headline)
                Text("Right-click the desktop → Edit Widgets → Unitutor → Study progress.\nYou can close this window.")
                    .font(.callout).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            .padding(30)
        }
        .windowResizability(.contentSize)
    }
}
