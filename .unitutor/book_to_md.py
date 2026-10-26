#!/usr/bin/env python3
"""Split a textbook PDF into one Markdown file per chapter (uses the PDF outline).

Usage: python3 .unitutor/book_to_md.py <book.pdf> <out_dir> [--chapters 12,13] [--prefix ch]

Writes <out_dir>/<prefix><N>.md with `<!-- page B (pdf P) -->` markers (B = printed page number)
and a `### N.M Title` heading where each section starts, plus <out_dir>/_index.md
(one line per chapter with its sections), for pasting into the course's .tutor/index.md.
Needs PyMuPDF (`pip install pymupdf`).
"""
import argparse
import re
import unicodedata
from pathlib import Path

import fitz


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("out_dir")
    ap.add_argument("--chapters", help="comma-separated chapter numbers (default: all)")
    ap.add_argument("--prefix", default="ch")
    a = ap.parse_args()

    doc = fitz.open(a.pdf)
    toc = doc.get_toc()
    chap_re = re.compile(r"^Chapter (\d+)\s+(.*)")
    sec_re = re.compile(r"^(\d+)\.(\d+)\s+(.*)")
    boundaries = [(p, t) for lvl, t, p in toc if lvl <= 2 and (t.startswith("PART") or t.startswith("Appendix") or t == "Index" or chap_re.match(t))]
    chapters = [(int(m.group(1)), m.group(2), p) for _, t, p in toc if (m := chap_re.match(t)) for p in [dict((tt, pp) for _, tt, pp in toc)[t]]]
    starts = sorted(p for p, _ in boundaries)
    first = next(p for n, _, p in chapters if n == 1)
    offset = first - 1  # printed page 1 = chapter 1 first page
    wanted = {int(x) for x in a.chapters.split(",")} if a.chapters else None

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for n, title, start in chapters:
        if wanted and n not in wanted:
            continue
        end = min((s for s in starts if s > start), default=len(doc) + 1) - 1
        secs = {}
        for _, t, p in toc:
            m = sec_re.match(t)
            if m and int(m.group(1)) == n and start <= p <= end:
                secs.setdefault(p, []).append(t)
        lines = [f"# Chapter {n} {title}", ""]
        for p in range(start, end + 1):
            lines.append(f"<!-- page {p - offset} (pdf {p}) -->")
            for t in secs.get(p, []):
                lines += [f"### {t}", ""]
            text = unicodedata.normalize("NFKC", doc[p - 1].get_text("text"))
            lines += [text.strip(), ""]
        (out / f"{a.prefix}{n}.md").write_text("\n".join(lines), encoding="utf-8")
        sec_list = "; ".join(f"{t} (p. {p - offset})" for p, ts in sorted(secs.items()) for t in ts
                             if not t.endswith(("Summary",)))
        index.append(f"- `md/book/{a.prefix}{n}.md`: Book chapter {n} – {title} (printed pp. {start - offset}–{end - offset}). Sections: {sec_list}")
        print(f"chapter {n}: pdf {start}-{end}")
    (out / "_index.md").write_text("\n".join(index) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
