# hdx-scraper-ebola_bundibugyo

Downloads xlsx resources from the HDX dataset
[republique-democratique-du-congo-cas-et-deces-d-ebola](https://data.humdata.org/dataset/republique-democratique-du-congo-cas-et-deces-d-ebola),
reads the "Data" sheet from each, and combines them into a single local CSV file
(`saved_data/combined_ebola_data.csv`) with an added "AsOf" column containing the
date parsed from each resource's description.

## Requirements

- Python 3.13+
- `~/.hdx_configuration.yaml` with HDX credentials, or env vars:
  `HDX_KEY`, `HDX_SITE`
- `~/.useragents.yaml` with a `hdx-scraper-ebola_bundibugyo` entry
- Optional: `USER_AGENT`, `TEMP_DIR`, `LOG_FILE_ONLY`

## Usage

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

Lint check:

```bash
pre-commit run --all-files
```

## Output

The combined CSV is written to `saved_data/combined_ebola_data.csv`.
Each row includes all columns from the original "Data" sheet plus an "AsOf"
column (ISO date, e.g. `2026-05-24`) derived from the resource description.
