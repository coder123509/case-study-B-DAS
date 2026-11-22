# Appendix - use of generative AI

_The brief requires this appendix: tools used, what we asked, what we changed.
Keep it honest and specific. Add a row every time you use an AI tool for this project._

| Date | Tool | What we asked | What it produced | What we checked / changed ourselves |
|---|---|---|---|---|
| 21 Nov 2026 | Claude (Anthropic) | Help locate public sources for Bengaluru 15-min AQ, weather, GTFS, OSM, BBMP flood points, holidays and news, and draft the download + cleaning + analysis pipeline for our proposal | Source search, download scripts, first drafts of `src/`, `sql/`, `spark/`, and docs | _e.g. re-ran every script, checked station ids against explore.openaq.org, re-typed / verified holiday dates against the PDF, reviewed cleaning thresholds, rewrote chart titles..._ |
| | | | | |

## What we verified by hand
- [ ] Every URL in `docs/source_register.md` opens and returns the data described
- [ ] Holiday CSV checked line by line against `data/raw/calendar/*.pdf`
- [ ] 10 random BBMP flood points checked against the PDF (name + coordinates)
- [ ] Each cleaning rule's example rows (`outputs/tables/outlier_examples.csv`) look right
- [ ] PySpark job run on our own laptop; row counts match `outputs/tables/spark_row_counts.csv`
- [ ] MySQL load + all 8 queries run in MySQL Workbench
- [ ] Every member can explain every script (Q&A)
