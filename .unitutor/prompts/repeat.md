Language: English only.

Review-only session on due topics, across courses. No new material.

Arguments: optional course name (default: all courses), optional max topics (default 8).

1. Read only `*/*/.tutor/progress.md` (or the one given course). Collect rows with `Due` <= today. Skip introduction lectures.
2. If none: say so, name the next upcoming `Due` (course, topic, date), and stop.
3. Report the queue size in one line. Order oldest `Due` first; interleave courses (avoid long same-course blocks). Cap at max topics.
4. For each topic: read only its relevant `.md` (via that course's `.tutor/index.md`). Ask 1 fresh question (new numbers, transfer or "why"; never the earlier one). One guiding question per reply, hints per `.unitutor/AGENTS.md`, no solutions, cite sources. Assess internally per "Assessing answers" in `.unitutor/AGENTS.md` (no explicit verdict; vague/incomplete answers get a Socratic pointer to the weak part and no promotion).
5. After each topic: update that course's `progress.md` per the ladder in `.unitutor/AGENTS.md` (status, Last seen = today, Due, 1 note). Keep existing rows.
6. After the queue (or `/end`): short recap (topic, course, old -> new status) and the next `Due` date. Stop.
