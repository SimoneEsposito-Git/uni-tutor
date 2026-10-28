// Übersicht desktop widget: study progress as donuts (green = known, blue = learning, red = new).
// Reads ~/Library/Application Support/Unitutor/progress.json, which progress.py rewrites on every progress update.
// COURSE = "" shows all courses; set a course name or initials ("Deep Learning", "dl") to show that course's lectures.
// For one widget per course, duplicate this folder and change COURSE (and the position below).
const COURSE = "";

export const command = `cat "$HOME/Library/Application Support/Unitutor/progress.json"`;
export const refreshFrequency = 60 * 1000;

export const className = `
  left: 24px; top: 24px; width: 340px; box-sizing: border-box; padding: 16px;
  border-radius: 20px; font: 13px -apple-system, system-ui, sans-serif;
  --bg: rgba(246,247,249,.92); --fg: #1d2330; --mute: #6b7280; --track: #e5e7eb;
  --new: #dc2626; --learning: #2563eb; --known: #16a34a;
  background: var(--bg); color: var(--fg); backdrop-filter: blur(20px);
  @media (prefers-color-scheme: dark) {
    --bg: rgba(17,19,24,.88); --fg: #e8eaee; --mute: #9aa1ad; --track: #2c313a;
    --new: #ef4444; --learning: #3b82f6; --known: #22c55e;
  }
  .head { display: flex; justify-content: space-between; align-items: baseline; font-weight: 600; font-size: 15px; margin-bottom: 12px; }
  .due { font-size: 12px; color: var(--new); } .due.ok { color: var(--known); }
  .main { display: flex; gap: 16px; align-items: flex-start; }
  .big { display: flex; flex-direction: column; gap: 6px; font-size: 11px; font-weight: 600; flex: none; }
  .rows { display: flex; flex-direction: column; gap: 9px; min-width: 0; }
  .row { display: flex; gap: 8px; align-items: center; }
  .name { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sub { font-size: 10.5px; color: var(--mute); } .sub.due { color: var(--new); }
  .upd { margin-top: 12px; font-size: 9px; color: var(--mute); }
`;

const donut = (c, size) => {
  const n = c.new + c.learning + c.known;
  const a = n ? (100 * c.known) / n : 0, b = n ? (100 * (c.known + c.learning)) / n : 0;
  const bg = n
    ? `conic-gradient(var(--known) 0 ${a}%, var(--learning) ${a}% ${b}%, var(--new) ${b}% 100%)`
    : "var(--track)";
  return (
    <div style={{ width: size, height: size, borderRadius: "50%", flex: "none", background: bg,
      WebkitMask: "radial-gradient(circle, transparent 57%, #000 58%)" }} />
  );
};

const initials = (s) => s.split(" ").map((x) => x[0]).join("").toLowerCase();

export const render = ({ output, error }) => {
  if (error || !output) return <div>Waiting for progress.json… {String(error || "")}</div>;
  const d = JSON.parse(output);
  const p = COURSE.toLowerCase().trim();
  const course = p && (d.courses.find((c) => c.course.toLowerCase() === p) ||
    d.courses.find((c) => c.course.toLowerCase().includes(p)) || d.courses.find((c) => initials(c.course) === p));
  if (p && !course) return <div>No course matches "{COURSE}"</div>;
  const sum = course || d;
  const rows = (course ? course.lectures : d.courses).filter((c) => c.topics > 0);
  return (
    <div>
      <div className="head">
        <span>{course ? course.course : "Study progress"}</span>
        <span className={"due" + (sum.due ? "" : " ok")}>{sum.due ? `${sum.due} due` : "all caught up"}</span>
      </div>
      <div className="main">
        <div className="big">
          {donut(sum, 96)}
          <span>{course ? "All lectures" : "All courses"}</span>
          <span className="sub">{sum.new + sum.learning + sum.known} topics</span>
        </div>
        <div className="rows">
          {rows.map((c) => (
            <div className="row" key={c.name || c.course}>
              {donut(c, 26)}
              <div style={{ minWidth: 0 }}>
                <div className="name">{c.name || c.course}</div>
                <div className={"sub" + (c.due ? " due" : "")}>
                  {c.due ? `${c.due} due · ` : ""}{c.known}/{c.topics} known
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="upd">Updated {d.updated}</div>
    </div>
  );
};
