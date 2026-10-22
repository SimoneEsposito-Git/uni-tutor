Language: English only.

Topic-based spaced repetition across courses, like Anki but per topic, not per card: each topic gets a freshly written question every time it comes up. The skill asks; the user answers.

Arguments: optional course (default: all), optional max reviews (default 8), optional new topics (default 3; "no new" = 0).

1. Run `python3 .unitutor/progress.py queue [course] --max <M> --new <K>` (Windows: `python .unitutor\progress.py ...`). It returns the session queue: due reviews (Due <= today, oldest first) with a few `new` topics (course order) mixed in, courses interleaved. Do not read `progress.md` yourself.
2. Report the queue size in one line. If it is empty: say so with the next Due it names, and stop.
3. For each topic in order: read only its lecture `.md` (via that course's `.tutor/index.md`), only the slides named in Source.
   - Review topic: ask one question on it. Use the Notes column to aim at the recorded gap.
   - New topic: the user has not studied it. Name the slides to read ("Lecture 2, slides 24-25") and wait for "ready", then ask an entry-level question (definition, core idea, "why"). Never explain the topic before the user has tried.
   - Questions: vary the type (definition from memory, "why", compare/contrast, apply to a small new example with new numbers, spot the error, transfer). Never repeat a question already asked this session or recorded in Notes; a topic that comes up again gets a new question.
   - Follow-ups, hints and assessment per `.unitutor/AGENTS.md` ("Asking questions" and "Assessing answers"): one guiding question per reply, no verdicts, no full solutions, cite sources.
4. After each topic, record the outcome: `python3 .unitutor/progress.py grade "<course>" "<topic>" pass|partial|fail --note "<concrete remaining gap>"`. pass = exam-ready without hint 3; partial = not exam-ready after the user's own restatement; fail = wrong or needed hint 3. The script applies the ladder (due dates, promotion, caps); do not compute them yourself.
5. Relearning: a topic graded partial or fail comes back once later in this session (after at least 2 other topics) with a different question. Grade that attempt too.
6. When the queue is done (or on `/end`): short recap table (Course | Topic | old -> new status), say plainly which topics are exam-ready and which still have gaps, and stop.
