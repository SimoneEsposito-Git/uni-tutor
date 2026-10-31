import SwiftUI

// Minimal host app: macOS only shows a widget if it ships inside an app. Open it once so the system registers the widget.
@main
struct UnitutorApp: App {
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
