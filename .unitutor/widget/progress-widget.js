// Scriptable widget: study progress as donut charts (green = known, blue = learning, red = new).
// Setup: Scriptable > Settings > File Bookmarks > add the iCloud Drive folder "Unitutor" as "Unitutor".
// No widget parameter = all courses. Parameter = course name or initials (e.g. "Deep Learning", "dl") = that course's lectures.
const fm = FileManager.local()
const file = fm.joinPath(fm.bookmarkedPath("Unitutor"), "progress.json")
await fm.downloadFileFromiCloud(file)
const d = JSON.parse(fm.readString(file))

// Same palette as overview.html. C = dynamic colours (follow the system), P = the current mode's colours for the donut
// images, which are drawn bitmaps and so cannot be dynamic; the widget redraws on every refresh.
const dark = Device.isUsingDarkAppearance()
const PAL = { bg: ["#f6f7f9", "#111318"], fg: ["#1d2330", "#e8eaee"], mute: ["#6b7280", "#9aa1ad"], track: ["#e5e7eb", "#2c313a"],
              new: ["#dc2626", "#ef4444"], learning: ["#2563eb", "#3b82f6"], known: ["#16a34a", "#22c55e"] }
const C = {}, P = {}
for (const [k, [l, dk]] of Object.entries(PAL)) { C[k] = Color.dynamic(new Color(l), new Color(dk)); P[k] = new Color(dark ? dk : l) }

// Filled ring segment from angle a0 to a1 (radians, 0 = top, clockwise), drawn as a polygon.
function segment(ctx, cx, cy, r, th, a0, a1, color) {
  const steps = Math.max(2, Math.ceil((a1 - a0) / 0.05)), p = new Path()
  const pt = (a, rr) => new Point(cx + rr * Math.sin(a), cy - rr * Math.cos(a))
  p.move(pt(a0, r))
  for (let i = 1; i <= steps; i++) p.addLine(pt(a0 + (a1 - a0) * i / steps, r))
  for (let i = steps; i >= 0; i--) p.addLine(pt(a0 + (a1 - a0) * i / steps, r - th))
  p.closeSubpath()
  ctx.setFillColor(color); ctx.addPath(p); ctx.fillPath()
}

function donut(c, size) {
  const ctx = new DrawContext()
  ctx.size = new Size(size, size); ctx.opaque = false; ctx.respectScreenScale = true
  const n = c.new + c.learning + c.known, r = size / 2 - 1, th = size * 0.17, g = n > 1 ? 0.04 : 0
  segment(ctx, size / 2, size / 2, r, th, 0, 2 * Math.PI - 0.0001, P.track)
  let a = 0
  for (const k of ["known", "learning", "new"]) {
    if (!c[k]) continue
    const span = 2 * Math.PI * c[k] / n
    segment(ctx, size / 2, size / 2, r, th, a + (span > g * 2 ? g / 2 : 0), a + span - (span > g * 2 ? g / 2 : 0), P[k])
    a += span
  }
  return ctx.getImage()
}

function txt(st, s, size, color, weight) {
  const t = st.addText(s); t.font = weight ? Font.semiboldSystemFont(size) : Font.systemFont(size)
  t.textColor = color; t.lineLimit = 1; return t
}

const param = (args.widgetParameter || "").toLowerCase().trim()
const initials = n => n.split(" ").map(x => x[0]).join("").toLowerCase()
const course = param && (d.courses.find(c => c.course.toLowerCase() === param) ||
  d.courses.find(c => c.course.toLowerCase().includes(param)) || d.courses.find(c => initials(c.course) === param))
const rows = (course ? course.lectures : d.courses).filter(c => c.topics > 0)
const sum = course || d
const unit = course ? "lectures" : "courses"
const nameOf = c => course ? c.name : c.course

async function main() {
const w = new ListWidget()
w.backgroundColor = C.bg
w.setPadding(16, 16, 16, 16)  // HIG content margin
w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000)
const fam = config.widgetFamily || "medium"
const dueTxt = sum.due ? `${sum.due} due` : "all caught up"
const dueCol = sum.due ? C.new : C.known
if (param && !course) { txt(w, `No course matches "${args.widgetParameter}"`, 12, C.new, true); Script.setWidget(w); return }

if (fam === "small") {
  const top = w.addStack(); top.centerAlignContent()
  txt(top, course ? course.course : "Study", 12, C.fg, true); top.addSpacer(); txt(top, dueTxt, 11, dueCol, true)
  w.addSpacer(4)
  const row = w.addStack(); row.addSpacer()
  row.addImage(donut(sum, 200)).imageSize = new Size(76, 76)
  row.addSpacer(); w.addSpacer(4)
  txt(w, `${sum.known} known · ${sum.learning} learning · ${sum.new} new`, 9, C.mute)
} else {
  const large = fam === "large", cap = large ? 7 : 8, shown = rows.slice(0, cap)
  const top = w.addStack(); top.centerAlignContent()
  txt(top, course ? course.course : "Study progress", large ? 15 : 13, C.fg, true)
  top.addSpacer(); txt(top, dueTxt, 11, dueCol, true)
  w.addSpacer(8)
  const main = w.addStack(); main.topAlignContent(); main.spacing = 14
  const left = main.addStack(); left.layoutVertically()
  const dsz = large ? 110 : 52
  left.addImage(donut(sum, 240)).imageSize = new Size(dsz, dsz)
  left.addSpacer(4)
  txt(left, course ? "All lectures" : "All courses", 11, C.fg, true)
  txt(left, `${sum.due} due · ${sum.known}/${sum.new + sum.learning + sum.known}`, 9, sum.due ? C.new : C.mute)
  const right = main.addStack(); right.layoutVertically(); right.spacing = large ? 8 : 4
  if (large) {  // one column, two text lines per row
    for (const c of shown) {
      const r = right.addStack(); r.centerAlignContent(); r.spacing = 7
      r.addImage(donut(c, 80)).imageSize = new Size(26, 26)
      const col = r.addStack(); col.layoutVertically()
      txt(col, nameOf(c), 12, C.fg)
      txt(col, c.due ? `${c.due} due · ${c.known}/${c.topics} known` : `${c.known}/${c.topics} known`, 9, c.due ? C.new : C.mute)
    }
  } else {  // medium: 4 rows x 2 columns, name only (red = something is due)
    for (let i = 0; i < shown.length; i += 2) {
      const line = right.addStack(); line.spacing = 10
      for (const c of shown.slice(i, i + 2)) {
        const cell = line.addStack(); cell.centerAlignContent(); cell.spacing = 6
        cell.size = new Size(104, 16)
        cell.addImage(donut(c, 64)).imageSize = new Size(16, 16)
        txt(cell, nameOf(c), 10.5, c.due ? C.new : C.fg).minimumScaleFactor = 0.85
      }
    }
  }
  w.addSpacer()
  if (rows.length > cap) txt(w, `+${rows.length - cap} more ${unit}`, 9, C.mute)
  else if (large) txt(w, `Updated ${d.updated}`, 8, C.mute)
}

if (config.runsInWidget) Script.setWidget(w); else await w.presentMedium()
}
await main()
Script.complete()
