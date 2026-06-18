import csv
import logging
from pathlib import Path

from hdx.api.configuration import Configuration
from hdx.data.dataset import Dataset
from hdx.location.adminlevel import AdminLevel
from hdx.utilities.dateparse import parse_date
from hdx.utilities.retriever import Retrieve

logger = logging.getLogger(__name__)

_DATASET_NAME = "republique-democratique-du-congo-cas-et-deces-d-ebola"
_DATASET_TITLE = "République démocratique du Congo : Cas et Décès d'Ebola"
_MAINTAINER = "7711391a-7647-4432-a71b-294e7f901a2c"
_OWNER_ORG = "fe22c15a-eea0-46b6-a10b-c40336236843"
_UPDATED_BY_SCRIPT = "HDX Scraper: Ebola Bundibugyo"
_TAGS = [
    "crisis-ebola-bundibugyo-virus-disease",
    "disease",
    "epidemics-outbreaks",
    "health",
]

# (config_key, measure, case_classification)
SOURCE_FILES = [
    ("confirmed_cases", "cases", "confirmed"),
    ("confirmed_deaths", "deaths", "confirmed"),
    ("suspected_cases", "cases", "suspected"),
    ("suspected_deaths", "deaths", "suspected"),
    ("contacts", "contacts", None),
]

OUTPUT_COLUMNS = [
    "location_country",
    "location_level",
    "location_name",
    "location_name_source",
    "location_code",
    "location_code_type",
    "reference_date",
    "measure",
    "case_classification",
    "time_period",
    "value",
    "unit",
    "source",
    "source_url",
    "source_indicator_name",
    "indicator_label",
    "reporting_period_start",
    "reporting_period_end",
    "last_updated",
    "data_quality_flag",
    "notes",
]

DEDUP_KEY = ["reference_date", "location_name", "measure", "case_classification"]


def normalise_date(value) -> str | None:
    if value is None or value == "":
        return None
    try:
        return parse_date(str(value)).date().isoformat()
    except Exception:
        return None


def _to_numeric(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_source_csv(
    path: Path,
    measure: str,
    case_classification: str | None,
    source_url: str,
    admin3: AdminLevel | None = None,
) -> list[dict]:
    rows_out = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nom = row.get("nom", "").strip()
            date_str = row.get("date", "").strip()
            if not nom or not date_str:
                continue
            ref_date = normalise_date(date_str)
            if ref_date is None:
                continue
            value_col = next((k for k in row if k not in ("nom", "date")), None)
            if value_col is None:
                continue
            value = _to_numeric(row[value_col])
            if value is None:
                continue
            if admin3 is not None:
                pcode, _ = admin3.get_pcode("COD", nom)
                location_code = pcode or ""
                location_code_type = "pcode" if pcode else "name"
                if location_code:
                    location_name = admin3.pcode_to_name[pcode]
                else:
                    location_name = nom
            else:
                location_code = ""
                location_code_type = "name"
                location_name = nom
            rows_out.append(
                {
                    "location_country": "COD",
                    "location_level": 3,
                    "location_name": location_name,
                    "location_name_source": nom,
                    "location_code": location_code,
                    "location_code_type": location_code_type,
                    "reference_date": ref_date,
                    "measure": measure,
                    "case_classification": case_classification,
                    "time_period": "cumulative",
                    "value": int(value),
                    "unit": "count",
                    "source": "INRB-UMIE",
                    "source_url": source_url,
                }
            )
    return rows_out


class Pipeline:
    def __init__(self, configuration: Configuration, retriever: Retrieve):
        self._configuration = configuration
        self._retriever = retriever

    def run(self) -> list[dict]:
        sources = self._configuration["sources"]

        logger.info("Setting up admin3 pcodes for COD")
        admin3 = AdminLevel(admin_level=3, retriever=self._retriever)
        admin3.setup_from_url(
            admin_url=AdminLevel.admin_all_pcodes_url,
            countryiso3s=["COD"],
        )

        all_rows: list[dict] = []
        for config_key, measure, classification in SOURCE_FILES:
            url = sources[config_key]
            logger.info(f"Downloading {config_key}: {url}")
            path = self._retriever.download_file(url)
            rows = _parse_source_csv(path, measure, classification, url, admin3)
            logger.info(f"  Parsed {len(rows)} rows")
            all_rows.extend(rows)

        seen: dict[tuple, dict] = {}
        for row in all_rows:
            key = tuple(row.get(k) for k in DEDUP_KEY)
            seen[key] = row
        return sorted(
            seen.values(), key=lambda r: tuple(r.get(k) or "" for k in DEDUP_KEY)
        )

    def generate_dataset(self, folder: Path, rows: list[dict]) -> Dataset:
        dates = [r["reference_date"] for r in rows if r.get("reference_date")]
        start_date = min(dates)
        end_date = max(dates)

        dataset = Dataset({"name": _DATASET_NAME, "title": _DATASET_TITLE})
        dataset.add_country_location("COD")
        dataset.set_maintainer(_MAINTAINER)
        dataset.set_organization(_OWNER_ORG)
        dataset.set_expected_update_frequency("Every day")
        dataset.set_time_period(start_date, end_date)
        dataset.set_subnational(True)
        dataset.add_tags(_TAGS)

        description = (
            f"Consolidation des cas et des décès liés à Ebola, désagrégés au niveau"
            f" administratif 3 du {start_date} au {end_date}"
        )
        resourcedata = {
            "name": "drc_ebola_cases_consolidated",
            "description": description,
        }
        dataset.generate_resource(
            folder,
            "drc_ebola_cases_consolidated.csv",
            rows,
            resourcedata,
            headers=OUTPUT_COLUMNS,
            no_empty=False,
        )
        return dataset
