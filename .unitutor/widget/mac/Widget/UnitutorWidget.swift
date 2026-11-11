import AppIntents
import SwiftUI
import WidgetKit

// MARK: - Data (written by .unitutor/progress.py to ~/Library/Application Support/Unitutor/progress.json)

struct Lecture: Decodable, Identifiable {
    var name: String
    var topics: Int, due: Int, new: Int, learning: Int, known: Int
    var `repeat`: Int? = nil   // subset of `learning` (status repeat); absent in older progress.json
    var id: String { name }
}

struct Course: Decodable, Identifiable {
    var course: String
    var topics: Int, due: Int, new: Int, learning: Int, known: Int
    var `repeat`: Int? = nil
    var lectures: [Lecture]
    var id: String { course }
}

struct Progress: Decodable {
    var updated: String
    var due: Int, new: Int, learning: Int, known: Int
    var `repeat`: Int? = nil
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
    let topics: Int, due: Int, new: Int, learning: Int, known: Int, rep: Int
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

/// Medium: 4 rows; 3 columns when a course's lectures are shown, 2 for the (longer) course names. Large: one column of 8.
func rowsPerPage(_ family: WidgetFamily, cols: Int) -> Int { family == .systemLarge ? 8 : 4 * cols }
func gridColumns(_ p: Progress, query: String?) -> Int { p.course(matching: query) != nil ? 3 : 2 }

func rowData(_ p: Progress, query: String?) -> [RowData] {
    if let c = p.course(matching: query) {
        return c.lectures.filter { $0.topics > 0 }.map {
            RowData(name: $0.name, topics: $0.topics, due: $0.due, new: $0.new, learning: $0.learning, known: $0.known, rep: $0.repeat ?? 0) }
    }
    return p.courses.filter { $0.topics > 0 }.map {
        RowData(name: $0.course, topics: $0.topics, due: $0.due, new: $0.new, learning: $0.learning, known: $0.known, rep: $0.repeat ?? 0) }
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
        let pages = p.map { p -> Int in
            let cap = rowsPerPage(context.family, cols: gridColumns(p, query: configuration.course))
            return (rowData(p, query: configuration.course).count + cap - 1) / cap
        } ?? 1
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
    static let learning = adaptive(light: 0x2563eb, dark: 0x3b82f6)   // ok, good
    static let relearn = adaptive(light: 0xdc2626, dark: 0xef4444)    // repeat
    static let new = adaptive(light: 0x9ca3af, dark: 0x6b7280)        // not studied yet
    static let due = adaptive(light: 0xdc2626, dark: 0xef4444)        // error text only
    static let track = adaptive(light: 0xe5e7eb, dark: 0x2c313a)
    static let icon = adaptive(light: 0x5c6370, dark: 0xa1a8b5)       // lecture / sheet icons in the donut holes
}

// MARK: - Icons (drawn in the same coordinate space as the SVG sketches; stretched to the given frame)

enum IconKind { case lecture, sheet }

/// Solid lecture icon (lecturer on a board above three students) or exercise sheet; details are cut out of the solid shape.
struct IconShape: View {
    let kind: IconKind

    var body: some View {
        Canvas { ctx, size in
            ctx.drawLayer { l in
                switch kind {
                case .lecture:
                    l.scaleBy(x: size.width / 214, y: size.height / 214)
                    l.translateBy(x: 7, y: 0)
                    l.fill(Path(roundedRect: CGRect(x: 10, y: 14, width: 180, height: 150), cornerRadius: 18), with: .foreground)
                    l.blendMode = .clear
                    l.fill(Path(ellipseIn: CGRect(x: 62, y: 36, width: 36, height: 36)), with: .foreground)
                    var body = Path()
                    body.move(to: CGPoint(x: 56, y: 175)); body.addLine(to: CGPoint(x: 56, y: 108))
                    body.addQuadCurve(to: CGPoint(x: 80, y: 84), control: CGPoint(x: 56, y: 84))
                    body.addLine(to: CGPoint(x: 90, y: 84))
                    body.addQuadCurve(to: CGPoint(x: 112, y: 108), control: CGPoint(x: 112, y: 84))
                    body.addLine(to: CGPoint(x: 112, y: 175)); body.closeSubpath()
                    l.fill(body, with: .foreground)
                    for cx in [45.0, 100, 155] {   // gap around each student head
                        let head = Path(ellipseIn: CGRect(x: cx - 17, y: 143, width: 34, height: 34))
                        l.fill(head, with: .foreground)
                        l.stroke(head, with: .foreground, lineWidth: 10)
                    }
                    l.blendMode = .normal
                    for cx in [45.0, 100, 155] {
                        l.fill(Path(ellipseIn: CGRect(x: cx - 17, y: 143, width: 34, height: 34)), with: .foreground)
                        l.fill(Path(roundedRect: CGRect(x: cx - 27, y: 180, width: 54, height: 30), cornerRadius: 15), with: .foreground)
                    }
                case .sheet:
                    l.scaleBy(x: size.width / 200, y: size.height / 200)
                    l.translateBy(x: 0, y: -5)
                    var page = Path()
                    page.move(to: CGPoint(x: 40, y: 26))
                    page.addArc(tangent1End: CGPoint(x: 40, y: 10), tangent2End: CGPoint(x: 56, y: 10), radius: 16)
                    page.addLine(to: CGPoint(x: 114, y: 10)); page.addLine(to: CGPoint(x: 160, y: 56))
                    page.addLine(to: CGPoint(x: 160, y: 188))
                    page.addArc(tangent1End: CGPoint(x: 160, y: 204), tangent2End: CGPoint(x: 144, y: 204), radius: 16)
                    page.addArc(tangent1End: CGPoint(x: 40, y: 204), tangent2End: CGPoint(x: 40, y: 188), radius: 16)
                    page.closeSubpath()
                    l.fill(page, with: .foreground)
                    l.blendMode = .clear
                    let round = StrokeStyle(lineWidth: 10, lineCap: .round, lineJoin: .round)
                    var fold = Path(); fold.move(to: CGPoint(x: 114, y: 8)); fold.addLine(to: CGPoint(x: 114, y: 56)); fold.addLine(to: CGPoint(x: 162, y: 56))
                    l.stroke(fold, with: .foreground, style: StrokeStyle(lineWidth: 7, lineCap: .round, lineJoin: .round))
                    for y in [94.0, 134] {
                        var tick = Path(); tick.move(to: CGPoint(x: 62, y: y)); tick.addLine(to: CGPoint(x: 71, y: y + 9)); tick.addLine(to: CGPoint(x: 87, y: y - 9))
                        l.stroke(tick, with: .foreground, style: round)
                        var line = Path(); line.move(to: CGPoint(x: 104, y: y)); line.addLine(to: CGPoint(x: 140, y: y))
                        l.stroke(line, with: .foreground, style: round)
                    }
                    l.stroke(Path(roundedRect: CGRect(x: 62, y: 162, width: 22, height: 22), cornerRadius: 4), with: .foreground, style: round)
                    var last = Path(); last.move(to: CGPoint(x: 104, y: 173)); last.addLine(to: CGPoint(x: 140, y: 173))
                    l.stroke(last, with: .foreground, style: round)
                }
            }
        }
    }
}

struct Counts {
    var new = 0, learning = 0, known = 0, rep = 0
    init(_ l: [Lecture]) {
        for x in l { new += x.new; learning += x.learning; known += x.known; rep += x.repeat ?? 0 }
    }
}

/// Donut with an icon in its hole (lecture or sheet totals).
struct IconDonut: View {
    let counts: Counts, kind: IconKind, size: CGFloat, line: CGFloat

    var body: some View {
        let w = (size - 2 * line) * 0.82
        ZStack {
            Donut(new: counts.new, learning: counts.learning, known: counts.known, rep: counts.rep, line: line)
            IconShape(kind: kind).foregroundStyle(Color.icon)
                .frame(width: w, height: w * 0.82)
        }
        .frame(width: size, height: size)
    }
}

struct Donut: View {
    let new: Int, learning: Int, known: Int, rep: Int   // learning includes rep (red); the blue ring is the rest
    var line: CGFloat

    var body: some View {
        let n = Double(new + learning + known)
        let blue = Double(max(0, learning - rep))
        let a = n > 0 ? Double(known) / n : 0
        let b = n > 0 ? (Double(known) + blue) / n : 0
        let c = n > 0 ? Double(known + learning) / n : 0
        ZStack {
            Circle().stroke(Color.track, lineWidth: line)
            if n > 0 {
                ring(0, a, .known)
                ring(a, b, .learning)
                ring(b, c, .relearn)
                ring(c, 1, .new)
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
            Donut(new: r.new, learning: r.learning, known: r.known, rep: r.rep, line: big ? 4.5 : 3)
                .frame(width: big ? 28 : 16, height: big ? 28 : 16)
            if big {
                VStack(alignment: .leading, spacing: 0) {
                    Text(r.name).font(.system(size: 12)).lineLimit(1)
                    Text("\(r.known)/\(r.topics) known")
                        .font(.system(size: 9)).foregroundStyle(.secondary).lineLimit(1)
                }
            } else {
                Text(r.name).font(.system(size: 10.5)).lineLimit(1).minimumScaleFactor(0.7)
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
            Text("No course matches \"\(q)\"").font(.caption).foregroundStyle(Color.due)
        } else {
            let title = course?.course ?? "Study progress"
            let counts = course.map { ($0.new, $0.learning, $0.known, $0.repeat ?? 0) } ?? (p.new, p.learning, p.known, p.repeat ?? 0)
            let lectures = (course.map { [$0] } ?? p.courses).flatMap(\.lectures)
            let isSheet = { (l: Lecture) in l.name.lowercased().hasPrefix("sheet") }
            let lecCounts = Counts(lectures.filter { !isSheet($0) }), sheetCounts = Counts(lectures.filter(isSheet))
            let cols = gridColumns(p, query: entry.query)
            let all = rowData(p, query: entry.query)
            let cap = rowsPerPage(family, cols: cols)
            let pages = max(1, (all.count + cap - 1) / cap)
            let page = entry.step % pages
            let rows = Array(all.dropFirst(page * cap).prefix(cap))

            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline) {
                    Text(title).font(.system(size: family == .systemLarge ? 15 : 13, weight: .semibold)).lineLimit(1)
                    Spacer(minLength: 6)
                    if family == .systemLarge {
                        Text("Updated \(p.updated)").font(.system(size: 8)).foregroundStyle(.secondary)
                    }
                }
                if family == .systemSmall {
                    Donut(new: counts.0, learning: counts.1, known: counts.2, rep: counts.3, line: 9)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    Text("\(counts.2) known · \(counts.1 - counts.3) ok · \(counts.3) repeat · \(counts.0) new")
                        .font(.system(size: 9)).foregroundStyle(.secondary).lineLimit(1).minimumScaleFactor(0.8)
                } else {
                    HStack(alignment: .top, spacing: family == .systemLarge ? 16 : 12) {
                        // Totals split in lectures (above) and sheets (below); the icon sits in the donut hole.
                        VStack(spacing: family == .systemLarge ? 10 : 6) {
                            IconDonut(counts: lecCounts, kind: .lecture, size: family == .systemLarge ? 96 : 46, line: family == .systemLarge ? 12 : 8)
                            IconDonut(counts: sheetCounts, kind: .sheet, size: family == .systemLarge ? 96 : 46, line: family == .systemLarge ? 12 : 8)
                        }
                        VStack(alignment: .leading, spacing: 0) {
                            if family == .systemLarge {
                                VStack(alignment: .leading, spacing: 8) {
                                    ForEach(rows) { Row(r: $0, big: true) }
                                }
                            } else {
                                Grid(alignment: .leading, horizontalSpacing: 8, verticalSpacing: 4) {
                                    ForEach(Array(stride(from: 0, to: rows.count, by: cols)), id: \.self) { i in
                                        GridRow {
                                            ForEach(0..<cols, id: \.self) { j in
                                                if i + j < rows.count { Row(r: rows[i + j], big: false) } else { Color.clear.frame(height: 1) }
                                            }
                                        }
                                    }
                                }
                            }
                            Spacer(minLength: 0)
                            // Footer at the bottom right: page dots (left) and the status counts (right), fixed on every page.
                            HStack(spacing: 6) {
                                if pages > 1 { PageDots(page: page, pages: pages) }
                                Spacer(minLength: 6)
                                // new • repeating • learning (ok/good) • solid (strong/solid), numbers in the donut colours
                                (Text("\(counts.0)").foregroundStyle(Color.new).fontWeight(.semibold) + Text(" new  •  ")
                                 + Text("\(counts.3)").foregroundStyle(Color.relearn).fontWeight(.semibold) + Text(" repeating  •  ")
                                 + Text("\(counts.1 - counts.3)").foregroundStyle(Color.learning).fontWeight(.semibold) + Text(" learning  •  ")
                                 + Text("\(counts.2)").foregroundStyle(Color.known).fontWeight(.semibold) + Text(" solid"))
                                    .font(.system(size: 10)).foregroundStyle(.secondary)
                                    .lineLimit(1).minimumScaleFactor(0.6)
                            }
                            .frame(height: 13)
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                    }
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
        .description("Donut charts of your lectures and sheets: new (grey), repeat (red), ok/good (blue), strong/solid (green). Set a course to see its lectures.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}
