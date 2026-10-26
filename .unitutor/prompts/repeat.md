Language: English only.

Topic-based spaced repetition across courses, like Anki but per topic, not per card: each topic gets a freshly written question every time it comes up. The skill asks; the user answers.

Arguments: optional course (default: all), optional max reviews (default 8), optional new topics (default 3; "no new" = 0).

1. Run `python3 .unitutor/progress.py queue [course] --max <M> --new <K>` (Windows: `python .unitutor\progress.py ...`). It returns the session queue: due reviews (Due <= today, oldest first) with a few `new` topics (course order) mixed in, courses interleaved. Do not read `progress.md` yourself.
2. Report the queue size in one line. If it is empty: say so with the next Due it names, and stop.
3. For each topic in order: read only the book section named in Source (`Book ch. X.Y`, via `.tutor/md/book/` and the course's `.tutor/index.md`); if there is none, the slides named in Source from the lecture `.md`. Check the slides too when the topic is exam-relevant detail the book may lack.
   - Review topic: ask one question on it. Use the Notes column to aim at the recorded gap.
   - New topic: the user has not studied it. Name the section to read ("Book ch. 12.3, pp. 563-567"; add the slides if the book lacks something they cover) and wait for "ready", then ask an entry-level question (definition, core idea, "why"). Never explain the topic before the user has tried.
   - Test understanding, not trivia: never ask for exact numbers, figures, versions, generations, acronym expansions or other memorised details (e.g. "how many GB/s?"). Ask about concepts, mechanisms, trade-offs, "why", and what a number implies (e.g. "which is faster and why?" or order-of-magnitude reasoning). Do not penalise missing exact figures in grading.
   - Questions: vary the type (definition from memory, "why", compare/contrast, apply to a small new example with new numbers, spot the error, transfer). Never repeat a question already asked this session or recorded in Notes; a topic that comes up again gets a new question.
   - Follow-ups, hints and assessment per `.unitutor/AGENTS.md` ("Asking questions" and "Assessing answers"): one guiding question per reply, no verdicts, no full solutions, cite sources.
4. After each topic, record the outcome: `python3 .unitutor/progress.py grade "<course>" "<topic>" pass|partial|fail --note "<concrete remaining gap>"`. grade by effort needed to reach the right answer: pass = correct or almost correct on the first try (small mistakes, imperfect wording, typos allowed); partial = needed one small hint/nudge (one tier down; `new`/`repeat` -> `ok`); fail = wrong, several follow-ups/corrections, hint 3, or looked up in the book/slides (`repeat`, which is reserved for topics to retry later in this same session). The script applies the ladder (due dates, promotion, caps); do not compute them yourself.
5. Relearning: a topic graded partial or fail comes back once later in this session (after at least 2 other topics) with a different question. Grade that attempt too.
6. When the queue is done (or on `/end`): short recap table (Course | Topic | old -> new status), say plainly which topics are exam-ready and which still have gaps, and stop.
