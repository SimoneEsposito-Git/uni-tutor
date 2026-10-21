Language: English only (cards, notes, recap).

Generates an Anki deck from one lecture or book chapter.

Arguments: course (or infer from context), and lecture/chapter (e.g. "Lecture 4", "ch. 6.2"). If either is ambiguous, ask once.

## Steps
1. Folder `*/<course>/` (the one containing `.tutor/`). Read `.tutor/index.md`, then only the `.md` of the chosen lecture/chapter. Source = lectures/book only (never `exercises/` or `solutions/`). Skip introduction lectures.
2. Select: only what the student must truly know (definitions, mechanisms, "why", key formulas, distinctions, typical pitfalls). Drop admin, anecdotes, trivia, one-off examples. Typical yield: 15-40 cards per lecture. Optional: weight topics with status `repeat` in `.tutor/progress.md`.
3. Write cards per the rules below, then self-check every card against the checklist; fix or drop failures.
4. Save to `generated/anki_<lecture>.tsv` (add `_2`, `_3`… if it exists). Write nothing else, outside `generated/`.
5. Reply short: card count, file path, how to import, topics skipped on purpose.

## Card rules (from Disputant, "Principles for High-Yield Cards", and "An Opinionated Guide to Using Anki Correctly")
- **Atomic**: one idea per card. Avoids cue overload; if a card cannot be split, the source was not understood: re-read it.
- **Questions, not statements**: test understanding ("Why…", "What happens if…", "How does X differ from Y"), never copy slide text as a fill-in-the-blank.
- **Short**: answer ~9 words, hard max 3 bullets. Several short cards beat one long one.
- **Future-proof**: the question must be answerable a month later without the slide. Name the topic/concept/law and add a specifier (e.g. "In a perceptron (hinge loss): what does the update rule do when a point is correctly classified?").
- **Holistic**: link new ideas to earlier ones (a "how does X relate to Y" card, a contrast with a similar concept). Add a pseudo-context/mnemonic in the Source field only if it genuinely helps.
- **No lists**: never one card for a list/set. Max 4 items, and only if tightly related; otherwise use several similar cards (one per item, or "what distinguishes…"). 
- **Basic cards only.** No cloze (it trains completing text, not recall); avoid image occlusion (slide images not exported).
- **No shortcuts**: do not reuse distinctive words from the answer in the question; keep prompts bland and consistently phrased; no decorative formatting.
- **Variety**: for core concepts, 2 differently phrased prompts (e.g. definition -> term, and term -> definition / "why") or a reverse card where sensible.
- **Handle/context card**: a topic with several cards gets one overview card ("Name the cards' topic: what are the 3 phases of X?" only if ≤4 items).
- **Source on the back**: after the answer, a small line `Source: Lecture 4, slide 12` plus (optional) a 1-sentence paraphrased excerpt, so a lapse can be fixed without opening the slides.

## Checklist (per card)
Atomic? Question (not statement)? Answer ≤ ~9 words / ≤ 3 bullets? Understandable cold in a month? No answer words in the question? Not a list > 4? Source cited?

## File format (Anki text import; tab-separated, UTF-8)
Header lines, then one note per line, columns: Front, Back, Tags.
```
#separator:tab
#html:true
#notetype:Basic
#deck:<Course name>
#tags column:3
<front><TAB><back><TAB><tags>
```
- Back = answer, then `<br><small>Source: Lecture 4, slide 12</small>`. Use `<br>` for line breaks, `<ul><li>` for bullets; no raw tabs or newlines inside a field.
- Math in MathJax: inline `\( … \)`, display `\[ … \]`.
- Tags: space-separated, hierarchical, no spaces inside: `<Course>::L4::<Topic>` (underscores for spaces).
