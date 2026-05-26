# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**hdx-scraper-ebola_bundibugyo** downloads xlsx resources from the HDX dataset
`republique-democratique-du-congo-cas-et-deces-d-ebola`, reads the "Data" sheet
from each resource, parses the date from the resource description (French text
like "… à la date du 24 mai 2026"), and writes a combined CSV to
`saved_data/combined_ebola_data.csv` with an added "AsOf" column.

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

1. **`parse_french_date`** — Extracts an ISO date from a French description string
   using a regex matching "à la date du DD MONTH YYYY".
2. **`main`** — Reads the HDX dataset, iterates over xlsx resources, downloads each
   to a temp directory, reads the "Data" sheet with pandas, adds the "AsOf" column,
   concatenates all DataFrames, and saves the result as a CSV.

### Key design points

- **No config files**: All configuration is hardcoded as constants (`DATASET_NAME`,
  `SHEET_NAME`, `OUTPUT_CSV`). There is no `config/` directory.
- **Read-only**: This scraper never writes to HDX; it only downloads data.
- **Output**: Written to `saved_data/` (git-ignored).

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
