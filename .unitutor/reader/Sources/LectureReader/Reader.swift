import SwiftUI
import PDFKit
import AppKit
import AVKit
import SwiftTerm

extension Notification.Name {
    static let findInDoc = Notification.Name("findInDoc")
    static let filterFiles = Notification.Name("filterFiles")
    static let findNext = Notification.Name("findNext")
    static let findPrev = Notification.Name("findPrev")
    static let toggleClaude = Notification.Name("toggleClaude")
    static let closeTab = Notification.Name("closeTab")
    static let nextTab = Notification.Name("nextTab")
    static let prevTab = Notification.Name("prevTab")
}

// MARK: - Model

struct Item: Identifiable, Hashable {
    let url: URL
    let title: String
    var id: URL { url }
    var isPDF: Bool { url.pathExtension.lowercased() == "pdf" }
}

struct ItemGroup: Identifiable {
    let id: String
    let title: String
    let items: [Item]
}

struct Course: Identifiable {
    let id: String
    let name: String
    let groups: [ItemGroup]
}

enum Scanner {
    static let folders = ["lectures", "exercises", "solutions", "info", "generated"]
    static let exts: Set<String> = ["pdf", "mp4", "mov", "m4v"]

    static func scan(_ root: URL) -> [Course] {
        let fm = FileManager.default
        let keys: [URLResourceKey] = [.isDirectoryKey]
        guard let dirs = try? fm.contentsOfDirectory(at: root, includingPropertiesForKeys: keys, options: [.skipsHiddenFiles]) else { return [] }
        return dirs
            .filter { (try? $0.resourceValues(forKeys: Set(keys)).isDirectory) == true }
            .sorted { $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending }
            .compactMap { dir -> Course? in
                var groups: [ItemGroup] = []
                for folder in folders {
                    let base = dir.appendingPathComponent(folder)
                    guard let en = fm.enumerator(at: base, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles]) else { continue }
                    var items: [Item] = []
                    for case let url as URL in en where exts.contains(url.pathExtension.lowercased()) {
                        let rel = url.path.replacingOccurrences(of: base.path + "/", with: "")
                        items.append(Item(url: url, title: (rel as NSString).deletingPathExtension))
                    }
                    items.sort { $0.title.localizedStandardCompare($1.title) == .orderedAscending }
                    if !items.isEmpty {
                        groups.append(ItemGroup(id: dir.lastPathComponent + "/" + folder, title: folder.capitalized, items: items))
                    }
                }
                return groups.isEmpty ? nil : Course(id: dir.lastPathComponent, name: dir.lastPathComponent, groups: groups)
            }
    }
}

final class Library: ObservableObject {
    @Published var courses: [Course] = []
    @Published var root: URL?

    init() {
        let d = UserDefaults.standard
        if let p = d.string(forKey: "root"), FileManager.default.fileExists(atPath: p) {
            root = URL(fileURLWithPath: p)
        } else {
            let guess = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Desktop/Master/Semester 1")
            if FileManager.default.fileExists(atPath: guess.path) { root = guess }
        }
        reload()
    }

    func reload() {
        guard let root else { courses = []; return }
        courses = Scanner.scan(root)
    }

    func chooseRoot() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.message = "Choose the folder that contains your course folders"
        if panel.runModal() == .OK, let url = panel.url {
            root = url
            UserDefaults.standard.set(url.path, forKey: "root")
            reload()
        }
    }
}

// MARK: - Claude pane

enum Tutor {
    /// The folder that holds `.unitutor` and the CLAUDE.md the course rules come from.
    static func projectDir(for root: URL) -> URL {
        var project = root
        while project.path != "/", !FileManager.default.fileExists(atPath: project.appendingPathComponent(".unitutor").path) {
            project = project.deletingLastPathComponent()
        }
        return project.path == "/" ? root : project
    }

    /// File the Claude session reads (via a UserPromptSubmit hook) to learn what the user is looking at.
    static let contextFile: URL = {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Lecture Reader", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("context.txt")
    }()

    static func writeContext(tab: DocTab?, page: Int?, root: URL?) {
        var text: String
        if let tab, let root {
            let rel = tab.url.path.replacingOccurrences(of: root.path + "/", with: "")
            let course = rel.components(separatedBy: "/").first ?? ""
            let md = root.appendingPathComponent(course).appendingPathComponent(".tutor/md")
                .appendingPathComponent(tab.url.deletingPathExtension().lastPathComponent + ".md")
            text = """
            [Lecture Reader context] The user is talking to you from the sidebar of their reader app. Treat the file below as the current reference for their message (as if it were attached) unless they clearly refer to something else.
            Course: \(course)
            File: \(tab.url.path)
            """
            if FileManager.default.fileExists(atPath: md.path) {
                text += "\nMarkdown version (read this rather than the PDF): \(md.path)"
            }
            if let page, let count = tab.reader?.view.document?.pageCount {
                text += "\nThey are on page/slide \(page) of \(count)."
            }
            if let sel = tab.reader?.userSelection {
                text += "\nSelected text (highlighted by the user in the reader; their message most likely refers to it):\n\"\"\"\n\(sel)\n\"\"\""
            }
        } else {
            text = "[Lecture Reader context] No file is open in the reader right now."
        }
        try? text.write(to: contextFile, atomically: true, encoding: .utf8)
    }
}

/// Terminal whose colors follow the system light/dark appearance.
final class ThemedTerminal: LocalProcessTerminalView {
    static var isDark: Bool {
        NSApp.effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
    }

    func applyTheme() {
        let dark = effectiveAppearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
        nativeBackgroundColor = dark ? NSColor(srgbRed: 0.12, green: 0.12, blue: 0.13, alpha: 1) : .white
        nativeForegroundColor = dark ? NSColor(srgbRed: 0.90, green: 0.90, blue: 0.91, alpha: 1) : NSColor(srgbRed: 0.10, green: 0.10, blue: 0.11, alpha: 1)
        caretColor = dark ? .white : .black
    }

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        applyTheme()
    }
}

final class ClaudeSession: NSObject, ObservableObject, LocalProcessTerminalViewDelegate {
    let terminal = ThemedTerminal(frame: .zero)
    @Published var running = false
    @Published var visible = false
    @Published var detached = false
    private var started = false

    override init() {
        super.init()
        terminal.processDelegate = self
        terminal.font = NSFont.monospacedSystemFont(ofSize: 13, weight: .regular)
        terminal.applyTheme()
    }

    /// Starts `claude` in the project folder, optionally with an initial prompt.
    func start(root: URL?, prompt: String?) {
        guard !running, let root else { return }
        let project = Tutor.projectDir(for: root)
        let script = """
        CLAUDE=$(command -v claude || ls -t "$HOME"/Library/Application\\ Support/Claude/claude-code/*/*/claude.app/Contents/MacOS/claude 2>/dev/null | head -1)
        if [ -z "$CLAUDE" ]; then echo "claude CLI not found"; exit 1; fi
        exec "$CLAUDE" "$@"
        """
        let settings: [String: Any] = [
            "showThinkingSummaries": false,
            "hooks": ["UserPromptSubmit": [["hooks": [["type": "command", "command": "cat '\(Tutor.contextFile.path)'"]]]]],
        ]
        let json = String(data: try! JSONSerialization.data(withJSONObject: settings), encoding: .utf8)!
        var args = ["-l", "-c", script, "zsh", "--settings", json]
        if let prompt { args.append(prompt) }
        terminal.feed(text: "\u{1b}c")
        terminal.startProcess(executable: "/bin/zsh", args: args,
                              environment: Terminal.getEnvironmentVariables(termName: "xterm-256color")
                                + ["COLORFGBG=" + (ThemedTerminal.isDark ? "15;0" : "0;15")],
                              currentDirectory: project.path)
        running = true
        started = true
    }

    func focus() {
        DispatchQueue.main.async { self.terminal.window?.makeFirstResponder(self.terminal) }
    }

    var hasStarted: Bool { started }

    func sizeChanged(source: LocalProcessTerminalView, newCols: Int, newRows: Int) {}
    func setTerminalTitle(source: LocalProcessTerminalView, title: String) {}
    func hostCurrentDirectoryUpdate(source: TerminalView, directory: String?) {}
    func processTerminated(source: TerminalView, exitCode: Int32?) {
        DispatchQueue.main.async { self.running = false }
    }
}

/// Hosts the shared terminal view; moving it to a new container (docked pane or detached window) re-parents it.
final class TerminalContainer: NSView {
    init(terminal: NSView) {
        super.init(frame: .zero)
        terminal.removeFromSuperview()
        terminal.frame = bounds
        terminal.autoresizingMask = [.width, .height]
        addSubview(terminal)
    }

    required init?(coder: NSCoder) { fatalError() }
}

struct ClaudeHost: NSViewRepresentable {
    let session: ClaudeSession
    func makeNSView(context: Context) -> TerminalContainer { TerminalContainer(terminal: session.terminal) }
    func updateNSView(_ nsView: TerminalContainer, context: Context) {}
}

struct ClaudePane: View {
    @ObservedObject var session: ClaudeSession
    @ObservedObject var ws: Workspace
    let root: URL?
    /// nil when the pane lives in its own window.
    var dock: Binding<String>?
    var onDetach: (() -> Void)?
    var onAttach: (() -> Void)?
    var onClose: (() -> Void)?

    private func dockButton(_ side: String, _ icon: String, _ help: String) -> some View {
        Button { dock?.wrappedValue = side } label: {
            Image(systemName: icon).foregroundStyle(dock?.wrappedValue == side ? Color.accentColor : .secondary)
        }
        .buttonStyle(.plain)
        .help(help)
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                Image(systemName: "sparkles")
                Text("Claude").fontWeight(.medium)
                Text(ws.reference)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Spacer()
                if dock != nil {
                    dockButton("right", "rectangle.righthalf.inset.filled", "Dock to the right")
                    dockButton("bottom", "rectangle.bottomhalf.inset.filled", "Dock to the bottom")
                    Button { onDetach?() } label: { Image(systemName: "arrow.up.forward.app") }
                        .buttonStyle(.plain)
                        .foregroundStyle(.secondary)
                        .help("Detach into its own window")
                    Button { onClose?() } label: { Image(systemName: "xmark") }
                        .buttonStyle(.plain)
                        .foregroundStyle(.secondary)
                        .help("Hide (⌘J)")
                } else {
                    Button { onAttach?() } label: { Image(systemName: "arrow.down.left.and.arrow.up.right") }
                        .buttonStyle(.plain)
                        .foregroundStyle(.secondary)
                        .help("Attach back to the main window")
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(.bar)
            ZStack {
                ClaudeHost(session: session)
                if !session.running {
                    VStack(spacing: 10) {
                        Text(session.hasStarted ? "Session ended" : "Claude is not running")
                            .foregroundStyle(.secondary)
                        Button(session.hasStarted ? "Restart" : "Start Claude") {
                            session.start(root: root, prompt: nil)
                            session.focus()
                        }
                    }
                    .padding(20)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 10))
                }
            }
        }
    }
}

// MARK: - PDF reader

final class Reader: ObservableObject {
    let view = PDFView()
    @Published var query = ""
    @Published var matches: [PDFSelection] = []
    @Published var index = 0
    @Published var title = ""
    private(set) var url: URL?
    private var restoring = false
    private var programmatic = false
    private(set) var userSelection: String?

    init() {
        view.autoScales = true
        view.displayMode = .singlePageContinuous
        view.displaysPageBreaks = true
        NotificationCenter.default.addObserver(forName: .PDFViewPageChanged, object: view, queue: .main) { [weak self] _ in
            guard let self, !self.restoring, let url = self.url,
                  let doc = self.view.document, let page = self.view.currentPage else { return }
            UserDefaults.standard.set(doc.index(for: page), forKey: "page:" + url.path)
        }
    }

    func load(_ url: URL) {
        guard let doc = PDFDocument(url: url) else { return }
        let saved = UserDefaults.standard.object(forKey: "page:" + url.path) as? Int
        restoring = true
        self.url = url
        title = url.deletingPathExtension().lastPathComponent
        clearSearch()
        view.document = doc
        DispatchQueue.main.async {
            if let saved, let page = doc.page(at: saved) { self.view.go(to: page) }
            self.restoring = false
        }
    }

    /// Remembers text the user highlighted (not search hits) so it can be sent as context.
    func captureSelection() {
        guard !programmatic else { return }
        let text = view.currentSelection?.string?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if text.isEmpty || (query.count >= 2 && !matches.isEmpty && index < matches.count && matches[index].string == view.currentSelection?.string) {
            userSelection = nil
        } else {
            userSelection = String(text.prefix(4000))
        }
    }

    var pageNumber: Int? {
        guard let doc = view.document, let page = view.currentPage else { return nil }
        return doc.index(for: page) + 1
    }

    func clearSearch() {
        query = ""
        matches = []
        index = 0
        view.highlightedSelections = nil
        view.clearSelection()
    }

    func find(_ q: String) {
        query = q
        guard let doc = view.document, q.count >= 2 else {
            matches = []; view.highlightedSelections = nil; view.clearSelection(); return
        }
        let found = doc.findString(q, withOptions: [.caseInsensitive, .diacriticInsensitive])
        found.forEach { $0.color = NSColor.systemYellow }
        matches = found
        index = 0
        view.highlightedSelections = found
        show()
    }

    func step(_ delta: Int) {
        guard !matches.isEmpty else { return }
        index = (index + delta + matches.count) % matches.count
        show()
    }

    private func show() {
        guard index < matches.count else { return }
        let s = matches[index]
        programmatic = true
        userSelection = nil
        view.setCurrentSelection(s, animate: true)
        view.go(to: s)
        programmatic = false
    }
}

struct VideoHost: NSViewRepresentable {
    let player: AVPlayer
    func makeNSView(context: Context) -> AVPlayerView {
        let v = AVPlayerView()
        v.controlsStyle = .floating
        v.player = player
        return v
    }
    func updateNSView(_ nsView: AVPlayerView, context: Context) { nsView.player = player }
}

struct PDFHost: NSViewRepresentable {
    let reader: Reader
    func makeNSView(context: Context) -> PDFView { reader.view }
    func updateNSView(_ nsView: PDFView, context: Context) {}
}

// MARK: - UI

// MARK: - Tabs

final class DocTab: ObservableObject, Identifiable {
    let id = UUID()
    let url: URL
    let reader: Reader?
    let player: AVPlayer?

    var title: String { url.deletingPathExtension().lastPathComponent }
    var isPDF: Bool { reader != nil }

    init(url: URL) {
        self.url = url
        if url.pathExtension.lowercased() == "pdf" {
            let r = Reader()
            r.load(url)
            reader = r
            player = nil
        } else {
            reader = nil
            player = AVPlayer(url: url)
        }
    }
}

final class Workspace: ObservableObject {
    @Published var tabs: [DocTab] = []
    @Published var active: UUID?
    @Published var page: Int?
    @Published var selectionChars = 0
    @Published var recents: [URL] = (UserDefaults.standard.stringArray(forKey: "recents") ?? [])
        .filter { FileManager.default.fileExists(atPath: $0) }
        .map { URL(fileURLWithPath: $0) }
    var root: URL?

    private func remember(_ url: URL) {
        recents.removeAll { $0 == url }
        recents.insert(url, at: 0)
        recents = Array(recents.prefix(6))
        UserDefaults.standard.set(recents.map(\.path), forKey: "recents")
    }

    var reference: String {
        guard let tab = current else { return "No file open" }
        var r = "Reference: " + tab.title
        if let page { r += " · p. \(page)" }
        if selectionChars > 0 { r += " · selection (\(selectionChars) chars)" }
        return r
    }

    init() {
        NotificationCenter.default.addObserver(forName: .PDFViewPageChanged, object: nil, queue: .main) { [weak self] n in
            guard let self, let view = n.object as? PDFView, view === self.current?.reader?.view else { return }
            self.refreshContext()
        }
        NotificationCenter.default.addObserver(forName: .PDFViewSelectionChanged, object: nil, queue: .main) { [weak self] n in
            guard let self, let view = n.object as? PDFView, view === self.current?.reader?.view else { return }
            self.current?.reader?.captureSelection()
            self.refreshContext()
        }
    }

    func refreshContext() {
        page = current?.reader?.pageNumber
        selectionChars = current?.reader?.userSelection?.count ?? 0
        Tutor.writeContext(tab: current, page: page, root: root)
    }

    var current: DocTab? { tabs.first { $0.id == active } }

    func open(_ url: URL) {
        remember(url)
        if let t = tabs.first(where: { $0.url == url }) {
            active = t.id
            save()
            return
        }
        let t = DocTab(url: url)
        tabs.append(t)
        active = t.id
        save()
    }

    func close(_ id: UUID) {
        guard let i = tabs.firstIndex(where: { $0.id == id }) else { return }
        tabs[i].player?.pause()
        tabs.remove(at: i)
        if active == id { active = tabs.isEmpty ? nil : tabs[min(i, tabs.count - 1)].id }
        save()
    }

    func cycle(_ delta: Int) {
        guard tabs.count > 1, let i = tabs.firstIndex(where: { $0.id == active }) else { return }
        active = tabs[(i + delta + tabs.count) % tabs.count].id
        save()
    }

    func move(_ id: UUID, before target: UUID) {
        guard id != target,
              let from = tabs.firstIndex(where: { $0.id == id }),
              let to = tabs.firstIndex(where: { $0.id == target }) else { return }
        let t = tabs.remove(at: from)
        tabs.insert(t, at: to)
        save()
    }

    func save() {
        let d = UserDefaults.standard
        d.set(tabs.map { $0.url.path }, forKey: "tabs")
        d.set(current?.url.path, forKey: "activeTab")
        refreshContext()
    }

    func restore() {
        let d = UserDefaults.standard
        let fm = FileManager.default
        for p in d.stringArray(forKey: "tabs") ?? [] where fm.fileExists(atPath: p) {
            open(URL(fileURLWithPath: p))
        }
        if let p = d.string(forKey: "activeTab"), let t = tabs.first(where: { $0.url.path == p }) {
            active = t.id
        }
    }
}

struct TabItem: View {
    @ObservedObject var tab: DocTab
    let isActive: Bool
    let select: () -> Void
    let close: () -> Void
    @State private var hover = false

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: tab.isPDF ? "doc.text" : "play.rectangle")
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(tab.title)
                .font(.callout)
                .lineLimit(1)
                .frame(maxWidth: 180, alignment: .leading)
            Button(action: close) { Image(systemName: "xmark").font(.caption2.weight(.bold)) }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .opacity(isActive || hover ? 1 : 0)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(isActive ? Color.accentColor.opacity(0.18) : (hover ? Color.primary.opacity(0.06) : .clear),
                    in: RoundedRectangle(cornerRadius: 6))
        .contentShape(Rectangle())
        .onTapGesture(perform: select)
        .onHover { hover = $0 }
    }
}

struct TabBar: View {
    @ObservedObject var ws: Workspace

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 2) {
                ForEach(ws.tabs) { tab in
                    TabItem(tab: tab, isActive: tab.id == ws.active,
                            select: { ws.active = tab.id; ws.save() },
                            close: { ws.close(tab.id) })
                        .draggable(tab.id.uuidString)
                        .dropDestination(for: String.self) { items, _ in
                            guard let s = items.first, let id = UUID(uuidString: s) else { return false }
                            ws.move(id, before: tab.id)
                            return true
                        }
                }
            }
            .padding(.horizontal, 6)
            .padding(.vertical, 4)
        }
        .background(.bar)
    }
}

struct PDFTabView: View {
    @ObservedObject var reader: Reader
    @FocusState private var findFocused: Bool

    private var findBar: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
            TextField("Find in document (⌘F)", text: Binding(get: { reader.query }, set: { reader.find($0) }))
                .textFieldStyle(.roundedBorder)
                .focused($findFocused)
                .onSubmit { reader.step(1) }
                .onKeyPress(.escape) {
                    reader.clearSearch()
                    findFocused = false
                    return .handled
                }
            Text(reader.query.count < 2 ? "" : reader.matches.isEmpty ? "No results" : "\(reader.index + 1)/\(reader.matches.count)")
                .font(.caption.monospacedDigit())
                .foregroundStyle(.secondary)
                .frame(minWidth: 60, alignment: .leading)
            Button { reader.step(-1) } label: { Image(systemName: "chevron.up") }
            Button { reader.step(1) } label: { Image(systemName: "chevron.down") }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(.bar)
    }

    var body: some View {
        VStack(spacing: 0) {
            findBar
            PDFHost(reader: reader)
        }
        .onReceive(NotificationCenter.default.publisher(for: .findInDoc)) { _ in findFocused = true }
        .onReceive(NotificationCenter.default.publisher(for: .findNext)) { _ in reader.step(1) }
        .onReceive(NotificationCenter.default.publisher(for: .findPrev)) { _ in reader.step(-1) }
    }
}

// MARK: - Welcome

struct WelcomeView: View {
    @ObservedObject var lib: Library
    @ObservedObject var ws: Workspace

    private func course(of url: URL) -> String {
        guard let root = lib.root else { return "" }
        return url.path.replacingOccurrences(of: root.path + "/", with: "").components(separatedBy: "/").first ?? ""
    }

    private func hint(_ keys: String, _ text: String) -> some View {
        HStack(spacing: 10) {
            Text(keys)
                .font(.system(.callout, design: .rounded).weight(.medium))
                .padding(.horizontal, 7)
                .padding(.vertical, 2)
                .background(Color.primary.opacity(0.08), in: RoundedRectangle(cornerRadius: 5))
                .frame(minWidth: 44)
            Text(text).foregroundStyle(.secondary)
            Spacer(minLength: 0)
        }
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 28) {
                VStack(spacing: 10) {
                    Image(nsImage: NSApp.applicationIconImage)
                        .resizable()
                        .frame(width: 84, height: 84)
                    Text("Lecture Reader").font(.system(size: 28, weight: .semibold, design: .rounded))
                    Text(lib.root == nil ? "Choose the folder that holds your courses to get started."
                         : "\(lib.courses.count) courses · pick a lecture from the sidebar or jump back in.")
                        .foregroundStyle(.secondary)
                }

                if lib.root == nil {
                    Button("Choose course folder…") { lib.chooseRoot() }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                } else if !ws.recents.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Recent").font(.headline)
                        VStack(spacing: 6) {
                            ForEach(ws.recents, id: \.self) { url in
                                Button { ws.open(url) } label: {
                                    HStack(spacing: 12) {
                                        Image(systemName: url.pathExtension.lowercased() == "pdf" ? "doc.text" : "play.rectangle")
                                            .font(.title3)
                                            .foregroundStyle(Color.accentColor)
                                            .frame(width: 28)
                                        VStack(alignment: .leading, spacing: 1) {
                                            Text(url.deletingPathExtension().lastPathComponent)
                                                .lineLimit(1)
                                            Text(course(of: url))
                                                .font(.caption)
                                                .foregroundStyle(.secondary)
                                        }
                                        Spacer(minLength: 0)
                                        Image(systemName: "chevron.right")
                                            .font(.caption)
                                            .foregroundStyle(.tertiary)
                                    }
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 9)
                                    .background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 10))
                                    .contentShape(RoundedRectangle(cornerRadius: 10))
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    .frame(maxWidth: 460)
                }

                VStack(alignment: .leading, spacing: 8) {
                    hint("⌘K", "Find a file")
                    hint("⌘F", "Search inside a PDF")
                    hint("⌘J", "Open Claude, with the current file as context")
                    hint("⌘W", "Close a tab")
                }
                .frame(maxWidth: 460)
            }
            .padding(40)
            .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - Main view


struct ContentView: View {
    @ObservedObject var lib: Library
    @ObservedObject var ws: Workspace
    @ObservedObject var claude: ClaudeSession
    @Environment(\.openWindow) private var openWindow
    @AppStorage("claudeDock") private var dock = "right"
    @State private var columns = NavigationSplitViewVisibility.automatic
    @State private var selection: URL?
    @State private var filter = ""
    @State private var expanded = Set(UserDefaults.standard.stringArray(forKey: "expanded") ?? [])
    @FocusState private var filterFocused: Bool

    private var filtered: [Course] {
        let q = filter.trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { return lib.courses }
        return lib.courses.compactMap { c in
            let gs = c.groups.compactMap { g -> ItemGroup? in
                let items = g.items.filter { $0.title.localizedCaseInsensitiveContains(q) || c.name.localizedCaseInsensitiveContains(q) }
                return items.isEmpty ? nil : ItemGroup(id: g.id, title: g.title, items: items)
            }
            return gs.isEmpty ? nil : Course(id: c.id, name: c.name, groups: gs)
        }
    }

    private func binding(_ key: String) -> Binding<Bool> {
        Binding(
            get: { !filter.isEmpty || expanded.contains(key) },
            set: { on in
                if on { expanded.insert(key) } else { expanded.remove(key) }
                UserDefaults.standard.set(Array(expanded), forKey: "expanded")
            })
    }

    private func toggleClaude() {
        if claude.detached {
            openWindow(id: "claude")
            claude.focus()
            return
        }
        claude.visible.toggle()
        guard claude.visible else { return }
        if !claude.running && !claude.hasStarted { claude.start(root: lib.root, prompt: nil) }
        claude.focus()
    }

    private func detachClaude() {
        if !claude.running && !claude.hasStarted { claude.start(root: lib.root, prompt: nil) }
        claude.detached = true
        openWindow(id: "claude")
    }

    private var documentArea: some View {
        VStack(spacing: 0) {
            if !ws.tabs.isEmpty { TabBar(ws: ws) }
            if let tab = ws.current {
                if let reader = tab.reader {
                    PDFTabView(reader: reader).id(tab.id)
                } else if let player = tab.player {
                    VideoHost(player: player).id(tab.id)
                }
            } else {
                WelcomeView(lib: lib, ws: ws)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var claudePane: some View {
        ClaudePane(session: claude, ws: ws, root: lib.root, dock: $dock,
                   onDetach: detachClaude, onClose: { claude.visible = false })
    }

    @ViewBuilder private var detail: some View {
        if !claude.visible || claude.detached {
            documentArea
        } else if dock == "bottom" {
            VSplitView {
                documentArea.frame(minHeight: 200)
                claudePane.frame(minHeight: 160, idealHeight: 340)
            }
        } else {
            HSplitView {
                documentArea.frame(minWidth: 300)
                claudePane.frame(minWidth: 320, idealWidth: 500)
            }
        }
    }

    var body: some View {
        NavigationSplitView(columnVisibility: $columns) {
            VStack(spacing: 0) {
                TextField("Filter files (⌘K)", text: $filter)
                    .textFieldStyle(.roundedBorder)
                    .focused($filterFocused)
                    .padding(8)
                    .onSubmit {
                        if let first = filtered.first?.groups.first?.items.first { selection = first.url }
                    }
                List(selection: $selection) {
                    ForEach(filtered) { course in
                        DisclosureGroup(isExpanded: binding(course.id)) {
                            ForEach(course.groups) { g in
                                DisclosureGroup(isExpanded: binding(g.id)) {
                                    ForEach(g.items) { item in
                                        Label(item.title, systemImage: item.isPDF ? "doc.text" : "play.rectangle")
                                            .lineLimit(1)
                                            .tag(item.url)
                                            .contextMenu {
                                                Button("Reveal in Finder") {
                                                    NSWorkspace.shared.activateFileViewerSelecting([item.url])
                                                }
                                            }
                                    }
                                } label: {
                                    Text(g.title).foregroundStyle(.secondary)
                                }
                            }
                        } label: {
                            Text(course.name).fontWeight(.semibold)
                        }
                    }
                }
                .listStyle(.sidebar)
            }
            .navigationSplitViewColumnWidth(min: 220, ideal: 280, max: 420)
            .toolbar {
                ToolbarItem {
                    Button { lib.chooseRoot() } label: { Image(systemName: "folder") }
                        .help("Choose course folder")
                }
            }
        } detail: {
            detail
                .navigationTitle(ws.current?.title ?? "Lecture Reader")
                .toolbar {
                    ToolbarItem {
                        Button { toggleClaude() } label: { Image(systemName: "sparkles") }
                            .help("Show or hide Claude (⌘J)")
                    }
                }
        }
        .onChange(of: selection) { _, new in
            if let new { ws.open(new) }
        }
        .onChange(of: ws.active) { _, _ in
            selection = ws.current?.url
            ws.tabs.forEach { if $0.id != ws.active { $0.player?.pause() } }
        }
        .onChange(of: lib.root) { _, new in
            ws.root = new
            ws.refreshContext()
        }
        .onAppear {
            ws.root = lib.root
            if ws.tabs.isEmpty { ws.restore() }
            ws.refreshContext()
            selection = ws.current?.url
        }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            lib.reload()
        }
        .onReceive(NotificationCenter.default.publisher(for: .toggleClaude)) { _ in toggleClaude() }
        .onReceive(NotificationCenter.default.publisher(for: .closeTab)) { _ in
            if let id = ws.active { ws.close(id) }
        }
        .onReceive(NotificationCenter.default.publisher(for: .nextTab)) { _ in ws.cycle(1) }
        .onReceive(NotificationCenter.default.publisher(for: .prevTab)) { _ in ws.cycle(-1) }
        .onReceive(NotificationCenter.default.publisher(for: .filterFiles)) { _ in
            if columns == .detailOnly {
                columns = .all
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { filterFocused = true }
            } else {
                filterFocused = true
            }
        }
    }
}

/// Content of the detached Claude window.
struct DetachedClaudeView: View {
    @ObservedObject var lib: Library
    @ObservedObject var ws: Workspace
    @ObservedObject var claude: ClaudeSession
    @Environment(\.dismissWindow) private var dismissWindow

    var body: some View {
        ClaudePane(session: claude, ws: ws, root: lib.root, dock: nil, onAttach: {
            claude.detached = false
            claude.visible = true
            dismissWindow(id: "claude")
            claude.focus()
        })
        .frame(minWidth: 380, minHeight: 280)
        .onAppear {
            // A restored window without an active detach has nothing to show.
            if !claude.detached { dismissWindow(id: "claude") } else { claude.focus() }
        }
        .onDisappear {
            // Closing the window re-docks the session instead of losing it.
            if claude.detached {
                claude.detached = false
                claude.visible = true
            }
        }
    }
}

@main
struct ReaderApp: App {
    @StateObject private var lib = Library()
    @StateObject private var ws = Workspace()
    @StateObject private var claude = ClaudeSession()

    var body: some Scene {
        Window("Lecture Reader", id: "main") {
            ContentView(lib: lib, ws: ws, claude: claude)
        }
        .defaultSize(width: 1250, height: 860)
        .commands {
            CommandGroup(replacing: .saveItem) {
                Button("Close Tab") { NotificationCenter.default.post(name: .closeTab, object: nil) }
                    .keyboardShortcut("w", modifiers: .command)
            }
            CommandGroup(replacing: .textEditing) {
                Button("Find in Document") { NotificationCenter.default.post(name: .findInDoc, object: nil) }
                    .keyboardShortcut("f", modifiers: .command)
                Button("Find Next") { NotificationCenter.default.post(name: .findNext, object: nil) }
                    .keyboardShortcut("g", modifiers: .command)
                Button("Find Previous") { NotificationCenter.default.post(name: .findPrev, object: nil) }
                    .keyboardShortcut("g", modifiers: [.command, .shift])
                Divider()
                Button("Show/Hide Claude") { NotificationCenter.default.post(name: .toggleClaude, object: nil) }
                    .keyboardShortcut("j", modifiers: .command)
                Button("Filter Files") { NotificationCenter.default.post(name: .filterFiles, object: nil) }
                    .keyboardShortcut("k", modifiers: .command)
            }
            CommandMenu("Tabs") {
                Button("Next Tab") { NotificationCenter.default.post(name: .nextTab, object: nil) }
                    .keyboardShortcut("]", modifiers: [.command, .shift])
                Button("Previous Tab") { NotificationCenter.default.post(name: .prevTab, object: nil) }
                    .keyboardShortcut("[", modifiers: [.command, .shift])
            }
        }

        Window("Claude", id: "claude") {
            DetachedClaudeView(lib: lib, ws: ws, claude: claude)
        }
        .defaultSize(width: 560, height: 760)
    }
}
