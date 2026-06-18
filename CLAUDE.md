# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**hdx-scraper-ebola_bundibugyo** downloads five cumulative CSV files from the
[INRB-UMIE GitHub repository](https://github.com/INRB-UMIE/BDBV2026-Data), transforms
them into a single long-format dataset, and publishes it to HDX as
[`republique-democratique-du-congo-cas-et-deces-d-ebola`](https://data.humdata.org/dataset/republique-democratique-du-congo-cas-et-deces-d-ebola).

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

1. **`pipeline.run()`** — Downloads the five source CSVs (confirmed/suspected cases and
   deaths, plus contacts), looks up DRC admin3 pcodes via `AdminLevel`, melts each into
   long-format rows, deduplicates on
   `(reference_date, location_name, measure, case_classification)`, and returns the
   sorted result.

2. **`pipeline.generate_dataset(folder, rows)`** — Constructs an HDX `Dataset` object
   using metadata from the template dataset, attaches a single CSV resource, and returns
   it for upload.

3. **`__main__.main`** — Wires the above together: `run()` → `generate_dataset()` →
   `update_from_yaml()` → `create_in_hdx()`.

### Wide → long column mapping

| Source column | `measure` | `case_classification` |
|---|---|---|
| confirmed cases CSV | `cases` | `confirmed` |
| confirmed deaths CSV | `deaths` | `confirmed` |
| suspected cases CSV | `cases` | `suspected` |
| suspected deaths CSV | `deaths` | `suspected` |
| contacts CSV | `contacts` | *(null)* |

### Key design points

- **`Retrieve`** (`hdx-python-utilities`) abstracts HTTP downloads and supports
  save/replay via `save=True`/`use_saved=True` — used in tests to replay fixture data
  from `tests/fixtures/input/`.
- **Static config inside the package**: `config/` lives under
  `src/hdx/scraper/ebola_bundibugyo/config/` so it is installed with the package and
  located via `script_dir_plus_file`.
- **`location_name_source`**: the raw `nom` value from the source CSV, preserved
  alongside the canonical `location_name` resolved from the pcode lookup.

### Config files

- `src/hdx/scraper/ebola_bundibugyo/config/project_configuration.yaml` — source CSV URLs
- `src/hdx/scraper/ebola_bundibugyo/config/hdx_dataset_static.yaml` — static HDX
  metadata applied to the dataset (license, methodology, source, notes, etc.)

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
