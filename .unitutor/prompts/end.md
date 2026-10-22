Language: English only.

Ends the current tutoring session.

1. Record every topic touched this session whose outcome is not yet saved, via `python3 .unitutor/progress.py grade "<course>" "<topic>" pass|partial|fail|seen --note "<concrete gap>"` (Windows: `python .unitutor\progress.py ...`). Outcome from the assessed answers ("Assessing answers" in `.unitutor/AGENTS.md`), not from how the session felt: unfinished or not exam-ready = partial; wrong or hint 3 = fail; explained in `/tutor` but not checked = seen. The script applies the ladder; never edit status or dates by hand. Skip introduction lectures.
2. Reply with one closing sentence only, e.g. "Progress has been updated, see you next session." No recap, no status list, no next-Due hint. Ask no further questions and do not continue tutoring.
