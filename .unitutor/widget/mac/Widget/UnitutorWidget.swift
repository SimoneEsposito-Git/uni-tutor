import AppIntents
import SwiftUI
import WidgetKit

// MARK: - Data (written by .unitutor/progress.py to ~/Library/Application Support/Unitutor/progress.json)

struct Lecture: Decodable, Identifiable {
    var name: String
    var topics: Int, due: Int, new: Int, learning: Int, known: Int
    var id: String { name }
}

struct Course: Decodable, Identifiable {
    var course: String
    var topics: Int, due: Int, new: Int, learning: Int, known: Int
    var lectures: [Lecture]
    var id: String { course }
}

struct Progress: Decodable {
    var updated: String
    var due: Int, new: Int, learning: Int, known: Int
    var courses: [Course]
    var topics: Int { new + learning + known }

    /// The sandbox hides the real home directory from NSHomeDirectory(), so ask the user database.
    static func load() -> Progress? {
        guard let pw = getpwuid(getuid()) else { return nil }
        let home = String(cString: pw.pointee.pw_dir)
        let url = URL(fileURLWithPath: home).appendingPathComponent("Library/Application Support/Unitutor/progress.json")
        guard let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(Progress.self, from: data)
    }

    func course(matching query: String?) -> Course? {
        let q = (query ?? "").lowercased().trimmingCharacters(in: .whitespaces)
        guard !q.isEmpty else { return nil }
        func initials(_ s: String) -> String { String(s.split(separator: " ").compactMap(\.first)).lowercased() }
        return courses.first { $0.course.lowercased() == q }
            ?? courses.first { $0.course.lowercased().contains(q) }
            ?? courses.first { initials($0.course) == q }
    }

    static let sample = Progress(updated: "", due: 4, new: 6, learning: 5, known: 3, courses: [
        Course(course: "Deep Learning", topics: 8, due: 2, new: 3, learning: 3, known: 2, lectures: [
            Lecture(name: "Lecture 1", topics: 4, due: 1, new: 1, learning: 2, known: 1),
            Lecture(name: "Lecture 2", topics: 4, due: 1, new: 2, learning: 1, known: 1)]),
        Course(course: "Database Technology", topics: 8, due: 2, new: 3, learning: 2, known: 1, lectures: [])])
}

// MARK: - Configuration (free text, like the widget parameter of the Scriptable widget)

struct CourseIntent: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "Course"
    static var description = IntentDescription("Leave empty for all courses, or enter a course name or its initials (e.g. dl) to show its lectures.")

    @Parameter(title: "Course")
    var course: String?
}

// MARK: - Paging (rows that don't fit are shown on further pages: automatic rotation + tap to advance)

struct RowData: Identifiable {
    let name: String
    let topics: Int, due: Int, new: Int, learning: Int, known: Int
    var id: String { name }
}

enum Pager {
    /// Seconds each page stays visible before the timeline switches to the next one.
    static let interval: TimeInterval = 5
    static let entries = 120   // 10 minutes of pages per timeline, then WidgetKit asks for a new one
    private static var defaults: UserDefaults { .standard }

    /// Unbounded page counter at `date`; the view takes it modulo its own page count.
    static func step(at date: Date) -> Int {
        let base = defaults.double(forKey: "pageBase"), start = defaults.integer(forKey: "pageStart")
        return start + max(0, Int((date.timeIntervalSinceReferenceDate - base) / interval))
    }

    /// Tap: go to the page after the one showing now and restart the rotation timer from there.
    static func advance() {
        defaults.set(step(at: .now) + 1, forKey: "pageStart")
        defaults.set(Date.now.timeIntervalSinceReferenceDate, forKey: "pageBase")
    }
}

struct NextPageIntent: AppIntent {
    static var title: LocalizedStringResource = "Next page"
    static var isDiscoverable = false

    func perform() async throws -> some IntentResult {
        Pager.advance()
        return .result()
    }
}

func rowsPerPage(_ family: WidgetFamily) -> Int { family == .systemLarge ? 8 : 8 }  // medium: 4 rows x 2 columns

func rowData(_ p: Progress, query: String?) -> [RowData] {
    if let c = p.course(matching: query) {
        return c.lectures.filter { $0.topics > 0 }.map {
            RowData(name: $0.name, topics: $0.topics, due: $0.due, new: $0.new, learning: $0.learning, known: $0.known) }
    }
    return p.courses.filter { $0.topics > 0 }.map {
        RowData(name: $0.course, topics: $0.topics, due: $0.due, new: $0.new, learning: $0.learning, known: $0.known) }
}

// MARK: - Timeline

struct Entry: TimelineEntry {
    let date: Date
    let progress: Progress?
    let query: String?
    var step = 0
}

struct Provider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> Entry { Entry(date: .now, progress: .sample, query: nil) }

    func snapshot(for configuration: CourseIntent, in context: Context) async -> Entry {
        Entry(date: .now, progress: context.isPreview ? .sample : Progress.load(), query: configuration.course)
    }

    func timeline(for configuration: CourseIntent, in context: Context) async -> Timeline<Entry> {
        let p = Progress.load()
        let pages = p.map { (rowData($0, query: configuration.course).count + rowsPerPage(context.family) - 1) / rowsPerPage(context.family) } ?? 1
        let now = Date.now
        // One entry per page change; a single entry when everything fits on one page.
        let dates = pages > 1 ? (0..<Pager.entries).map { now.addingTimeInterval(Double($0) * Pager.interval) } : [now]
        let entries = dates.map { Entry(date: $0, progress: p, query: configuration.course, step: Pager.step(at: $0)) }
        return Timeline(entries: entries, policy: .after(now.addingTimeInterval(pages > 1 ? Double(Pager.entries) * Pager.interval : 15 * 60)))
    }
}

// MARK: - Views

extension Color {
    /// Same palette as overview.html, adapting to the system appearance.
    static func adaptive(light: UInt32, dark: UInt32) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            let isDark = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            let v = isDark ? dark : light
            return NSColor(srgbRed: CGFloat((v >> 16) & 0xff) / 255, green: CGFloat((v >> 8) & 0xff) / 255,
                           blue: CGFloat(v & 0xff) / 255, alpha: 1)
        })
    }
    static let known = adaptive(light: 0x16a34a, dark: 0x22c55e)
    static let learning = adaptive(light: 0x2563eb, dark: 0x3b82f6)
    static let new = adaptive(light: 0xdc2626, dark: 0xef4444)
    static let track = adaptive(light: 0xe5e7eb, dark: 0x2c313a)
}

struct Donut: View {
    let new: Int, learning: Int, known: Int
    var line: CGFloat

    var body: some View {
        let n = Double(new + learning + known)
        let a = n > 0 ? Double(known) / n : 0
        let b = n > 0 ? Double(known + learning) / n : 0
        ZStack {
            Circle().stroke(Color.track, lineWidth: line)
            if n > 0 {
                ring(0, a, .known)
                ring(a, b, .learning)
                ring(b, 1, .new)
            }
        }
        .padding(line / 2)
    }

    @ViewBuilder private func ring(_ from: Double, _ to: Double, _ color: Color) -> some View {
        if to > from {
            Circle().trim(from: from, to: to)
                .stroke(color, style: StrokeStyle(lineWidth: line, lineCap: .butt))
                .rotationEffect(.degrees(-90))
        }
    }
}

struct Row: View {
    let r: RowData
    let big: Bool   // large: single column with a "due · known/total" subtext; medium: compact grid cell, name only

    var body: some View {
        HStack(spacing: 6) {
            Donut(new: r.new, learning: r.learning, known: r.known, line: big ? 4.5 : 3)
                .frame(width: big ? 28 : 16, height: big ? 28 : 16)
            if big {
                VStack(alignment: .leading, spacing: 0) {
                    Text(r.name).font(.system(size: 12)).lineLimit(1)
                    Text(r.due > 0 ? "\(r.due) due · \(r.known)/\(r.topics) known" : "\(r.known)/\(r.topics) known")
                        .font(.system(size: 9)).foregroundStyle(r.due > 0 ? Color.new : .secondary).lineLimit(1)
                }
            } else {
                Text(r.name).font(.system(size: 10.5)).lineLimit(1).minimumScaleFactor(0.85)
                    .foregroundStyle(r.due > 0 ? Color.new : .primary)   // red name = something is due
            }
        }
    }
}

/// Page dots; tapping them shows the next page.
struct PageDots: View {
    let page: Int, pages: Int

    var body: some View {
        Button(intent: NextPageIntent()) {
            HStack(spacing: 4) {
                ForEach(0..<pages, id: \.self) { i in
                    Circle().fill(i == page ? Color.primary : Color.secondary.opacity(0.35)).frame(width: 5, height: 5)
                }
            }
            .padding(.vertical, 1)
        }
        .buttonStyle(.plain)
    }
}

struct WidgetView: View {
    let entry: Entry
    @Environment(\.widgetFamily) private var family

    var body: some View {
        if let p = entry.progress {
            content(p)
        } else {
            Text("No progress yet. Run /sync or study a topic.").font(.caption).foregroundStyle(.secondary)
        }
    }

    @ViewBuilder private func content(_ p: Progress) -> some View {
        let course = p.course(matching: entry.query)
        if let q = entry.query, !q.trimmingCharacters(in: .whitespaces).isEmpty, course == nil {
            Text("No course matches \"\(q)\"").font(.caption).foregroundStyle(Color.new)
        } else {
            let title = course?.course ?? "Study progress"
            let due = course?.due ?? p.due
            let counts = course.map { ($0.new, $0.learning, $0.known) } ?? (p.new, p.learning, p.known)
            let total = counts.0 + counts.1 + counts.2
            let all = rowData(p, query: entry.query)
            let cap = rowsPerPage(family)
            let pages = max(1, (all.count + cap - 1) / cap)
            let page = entry.step % pages
            let rows = Array(all.dropFirst(page * cap).prefix(cap))

            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline) {
                    Text(title).font(.system(size: family == .systemLarge ? 15 : 13, weight: .semibold)).lineLimit(1)
                    Spacer()
                    Text(due > 0 ? "\(due) due" : "all caught up").font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(due > 0 ? Color.new : .known)
                }
                if family == .systemSmall {
                    Donut(new: counts.0, learning: counts.1, known: counts.2, line: 9)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    Text("\(counts.2) known · \(counts.1) learning · \(counts.0) new")
                        .font(.system(size: 9)).foregroundStyle(.secondary).lineLimit(1)
                } else {
                    HStack(alignment: .top, spacing: 16) {
                        VStack(alignment: .leading, spacing: 4) {
                            Donut(new: counts.0, learning: counts.1, known: counts.2, line: family == .systemLarge ? 14 : 11)
                                .frame(width: family == .systemLarge ? 110 : 52, height: family == .systemLarge ? 110 : 52)
                            Text(course == nil ? "All courses" : "All lectures").font(.system(size: 11, weight: .semibold))
                            Text("\(due) due · \(counts.2)/\(total)").font(.system(size: 9))
                                .foregroundStyle(due > 0 ? Color.new : .secondary).lineLimit(1)
                        }
                        if family == .systemLarge {
                            VStack(alignment: .leading, spacing: 8) {
                                ForEach(rows) { Row(r: $0, big: true) }
                            }
                        } else {
                            Grid(alignment: .leading, horizontalSpacing: 10, verticalSpacing: 4) {
                                ForEach(Array(stride(from: 0, to: rows.count, by: 2)), id: \.self) { i in
                                    GridRow {
                                        Row(r: rows[i], big: false)
                                        if i + 1 < rows.count { Row(r: rows[i + 1], big: false) } else { Color.clear.frame(height: 1) }
                                    }
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        Spacer(minLength: 0)
                    }
                    Spacer(minLength: 0)
                    // Fixed footer: the dots stay in the same place on every page.
                    ZStack {
                        if pages > 1 { PageDots(page: page, pages: pages) }
                        if family == .systemLarge {
                            Text("Updated \(p.updated)").font(.system(size: 8)).foregroundStyle(.secondary)
                                .frame(maxWidth: .infinity, alignment: .trailing)
                        }
                    }
                    .frame(height: 11)
                }
            }
            // Pin everything to the top-left so the title and the big donut never move when a page has fewer rows.
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
    }
}

// MARK: - Widget

@main
struct UnitutorWidget: Widget {
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: "UnitutorProgress", intent: CourseIntent.self, provider: Provider()) { entry in
            WidgetView(entry: entry).containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("Study progress")
        .description("Donut charts of your topics: known, learning, new. Set a course to see its lectures.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}
