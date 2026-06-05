# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**hdx-scraper-ebola_bundibugyo** downloads a single Google Sheets xlsx (URL in
`config/project_configuration.yaml`), reads each date-named tab (e.g. `260524`),
transforms the wide-format data into a long/tidy format, and writes the result to
`output_data/combined_ebola_data.csv`.

## Commands

Install dependencies:
```bash
uv sync
```

Run the scraper:
```bash
uv run python -m hdx.scraper.ebola_bundibugyo
```

Run tests:
```bash
uv run pytest
```

Run a single test:
```bash
uv run pytest tests/test_ebola_bundibugyo.py
```

Lint check:
```bash
pre-commit run --all-files
```

## Architecture

The pipeline in `__main__.py`:

1. **`normalise_date`** — Converts various date representations (Timestamp, ISO
   string, locale strings like "5/19/2026") to an ISO date string.
2. **`transform_tab`** — Takes a wide-format date tab DataFrame and melts it into
   long/tidy rows. Skips rows with null `Date` or `Admin3Pcode`. Coerces non-numeric
   cells (e.g. "ND") to NaN and omits those measures from the output.
3. **`main`** — Reads the `xlsx_file` URL from `config/project_configuration.yaml`,
   downloads the xlsx, reads the `Metadata` tab to enumerate date tabs, calls
   `transform_tab` on each, deduplicates on
   `(reference_date, location_code, measure, case_classification)` keeping the
   latest tab's values, and saves the result to `output_data/combined_ebola_data.csv`.

### Wide → long column mapping

| Source column | `measure` | `case_classification` |
|---|---|---|
| `CasSuspect` | `cases` | `suspected` |
| `DecesSuspect` | `deaths` | `suspected` |
| `CasConfirmes` | `cases` | `confirmed` |
| `DecesConfirmes` | `deaths` | `confirmed` |
| `CasProbable` | `cases` | `probable` |
| `Contacts` | `contacts` | *(null)* |
| `Gueris` | `cases` | `recovered` |

### Key design points

- **Config file**: `config/project_configuration.yaml` holds `xlsx_file` (prod and
  test variants). The prod URL is commented out; the test URL is active.
- **Read-only**: This scraper never writes to HDX; it only downloads data.
- **Output**: Written to `output_data/` (git-ignored).

## Environment

Requires `~/.hdx_configuration.yaml` with HDX credentials, or env vars:
`HDX_KEY`, `HDX_SITE`, `USER_AGENT`, `TEMP_DIR`, `LOG_FILE_ONLY`.

Requires `~/.useragents.yaml` with a `hdx-scraper-ebola_bundibugyo` entry.

## Collaboration Style

- Be objective, not agreeable. Act as a partner, not a sycophant. Push back when you disagree, flag tradeoffs honestly, and don't sugarcoat problems.
- Keep explanations brief and to the point.
- Don't rely on recalled knowledge for facts that could be stale (API behaviour, library versions, external systems). Search or read the actual source first.

## Scope of Changes

When fixing a bug or addressing PR feedback, change only what is necessary to resolve the specific issue. Do not refactor surrounding code, rename variables, adjust formatting, or make improvements in the same commit unless they are directly required by the fix.
