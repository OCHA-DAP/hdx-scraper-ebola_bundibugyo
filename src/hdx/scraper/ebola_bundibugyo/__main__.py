import csv
import json
import logging
import re
import tempfile
from os import getenv
from pathlib import Path

import gspread
from hdx.api.configuration import Configuration
from hdx.facades.infer_arguments import facade
from hdx.location.adminlevel import AdminLevel
from hdx.location.country import Country
from hdx.pipelineutils.hapi_admins import complete_admins
from hdx.utilities.dateparse import parse_date
from hdx.utilities.downloader import Download
from hdx.utilities.easy_logging import setup_logging
from hdx.utilities.retriever import Retrieve

from ._version import __version__

setup_logging()
logger = logging.getLogger(__name__)

lookup = "hdx-scraper-ebola_bundibugyo"
OUTPUT_DIR = Path("output_data")
OUTPUT_CSV = OUTPUT_DIR / "combined_ebola_data.csv"

MEASURE_MAP = [
    ("CasSuspect", "cases", "suspected"),
    ("DecesSuspect", "deaths", "suspected"),
    ("CasConfirmes", "cases", "confirmed"),
    ("DecesConfirmes", "deaths", "confirmed"),
    ("CasProbable", "cases", "probable"),
    ("Contacts", "contacts", None),
    ("Gueris", "cases", "recovered"),
]

OUTPUT_COLUMNS = [
    "location_country",
    "location_level",
    "location_name",
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

DEDUP_KEY = ["reference_date", "location_code", "measure", "case_classification"]


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


def _prefix_to_iso3(pcode: str) -> str | None:
    """Extract country ISO3 from the leading letters of a pcode."""
    m = re.match(r"^([A-Za-z]+)", pcode)
    if not m:
        return None
    letters = m.group(1).upper()
    if len(letters) == 2:
        return Country.get_iso3_from_iso2(letters, use_live=False)
    return letters[:3]


def _setup_admins(
    retriever: Retrieve, countryiso3s: list[str] | None
) -> list[AdminLevel]:
    admins = []
    for i in range(3):
        admin = AdminLevel(admin_level=i + 1, retriever=retriever)
        if i == 2:
            admin.setup_from_url(
                admin_url=AdminLevel.admin_all_pcodes_url,
                countryiso3s=countryiso3s,
            )
        else:
            admin.setup_from_url(countryiso3s=countryiso3s)
        admin.load_pcode_formats()
        admins.append(admin)
    return admins


def _infer_countryiso3s(tab_data: dict[str, list[dict]]) -> list[str] | None:
    """Scan pcode columns across all tabs to identify country ISO3s."""
    pcode_cols = [f"Admin{n}Pcode" for n in range(3, 0, -1)]
    iso3s = set()
    for records in tab_data.values():
        for record in records:
            for col in pcode_cols:
                pcode = str(record.get(col, ""))
                if pcode and pcode != "None":
                    iso3 = _prefix_to_iso3(pcode)
                    if iso3:
                        iso3s.add(iso3)
                    break
    return sorted(iso3s) if iso3s else None


def _row_str(record: dict, col: str) -> str:
    val = record.get(col)
    return "" if val is None or val == "" else str(val)


def transform_tab(
    records: list[dict],
    reporting_period_start: str | None,
    reporting_period_end: str | None,
    admins: list[AdminLevel],
) -> list[dict]:
    """Convert wide-format date tab records to long-format rows.

    reference_date is taken from each record's Date field. reporting_period_start
    and reporting_period_end come from the Metadata tab. complete_admins is called
    per row to validate/complete pcodes and derive location_country, location_level,
    and location_code_type.
    """
    if not records:
        return []

    highest_pcode_col = next(
        (f"Admin{n}Pcode" for n in range(3, 0, -1) if f"Admin{n}Pcode" in records[0]),
        None,
    )
    if not highest_pcode_col:
        return []

    rows_out = []
    for record in records:
        if not record.get("Date") or not record.get(highest_pcode_col):
            continue

        provider_adm_names = [_row_str(record, f"Admin{n}") for n in range(1, 4)]
        adm_codes = [_row_str(record, f"Admin{n}Pcode") for n in range(1, 4)]
        adm_names = ["", "", ""]

        countryiso3 = None
        for n in range(3, 0, -1):
            code = adm_codes[n - 1]
            if code:
                countryiso3 = admins[n - 1].pcode_to_iso3.get(
                    code.upper()
                ) or _prefix_to_iso3(code)
                if countryiso3:
                    break

        if not countryiso3:
            logger.warning(f"Could not determine country for pcodes: {adm_codes}")
            continue

        adm_level, warnings = complete_admins(
            admins, countryiso3, provider_adm_names, adm_codes, adm_names
        )
        for warning in warnings:
            logger.warning(warning)

        location_code = adm_codes[adm_level - 1] if adm_level else ""
        location_name = adm_names[adm_level - 1] if adm_level else ""
        location_code_type = "pcode" if location_code else "name"

        ref_date = normalise_date(record.get("Date"))
        if ref_date is None:
            continue

        for col, measure, classification in MEASURE_MAP:
            value = _to_numeric(record.get(col))
            if value is None:
                continue
            rows_out.append(
                {
                    "location_country": countryiso3,
                    "location_level": adm_level,
                    "location_name": location_name,
                    "location_code": location_code,
                    "location_code_type": location_code_type,
                    "reference_date": ref_date,
                    "measure": measure,
                    "case_classification": classification,
                    "time_period": "cumulative",
                    "value": int(value),
                    "unit": "count",
                    "reporting_period_start": reporting_period_start,
                    "reporting_period_end": reporting_period_end,
                }
            )

    return rows_out


def main(gsheet_auth: str | None = None) -> None:
    """Download DRC Ebola data from a Google Sheet and write a long-format CSV.

    Args:
        gsheet_auth (str | None): Google Sheets service account. Defaults to None.
    Returns:
        None
    """
    logger.info(f"##### {lookup} version {__version__} ####")

    if gsheet_auth is None:
        gsheet_auth = getenv("GSHEET_AUTH")

    configuration = Configuration.read()
    spreadsheet_url = configuration["google_sheet"]

    info = json.loads(gsheet_auth)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    gc = gspread.service_account_from_dict(info, scopes=scopes)
    logger.info(f"Opening Google Sheet: {spreadsheet_url}")
    spreadsheet = gc.open_by_url(spreadsheet_url)

    worksheet_titles = {ws.title for ws in spreadsheet.worksheets()}

    metadata_records = spreadsheet.worksheet("Metadata").get_all_records()
    metadata = {
        str(r["tab_name"]): r
        for r in metadata_records
        if str(r["tab_name"]) in worksheet_titles
    }
    tab_names = sorted(metadata)

    # Read all tab data into memory before setting up admin lookups
    tab_data = {}
    for tab_name in tab_names:
        logger.info(f"Reading tab {tab_name}")
        tab_data[tab_name] = spreadsheet.worksheet(tab_name).get_all_records()

    countryiso3s = _infer_countryiso3s(tab_data)
    logger.info(f"Inferred countries: {countryiso3s}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        with Download() as downloader:
            retriever = Retrieve(downloader, tmp_dir, tmp_dir, tmp_dir)
            admins = _setup_admins(retriever, countryiso3s)

    all_rows: list[dict] = []
    for tab_name in tab_names:
        meta = metadata[tab_name]
        period_start = normalise_date(meta["reporting_period_start"])
        period_end = normalise_date(meta["reporting_period_end"])
        logger.info(f"Processing tab {tab_name}")
        records = tab_data[tab_name]
        if not records:
            continue
        all_rows.extend(transform_tab(records, period_start, period_end, admins))

    if not all_rows:
        logger.warning("No data found!")
        return

    # Dedup on (reference_date, location_code, measure, case_classification), keep last
    seen: dict[tuple, dict] = {}
    for row in all_rows:
        key = tuple(row.get(k) for k in DEDUP_KEY)
        seen[key] = row
    rows = sorted(seen.values(), key=lambda r: tuple(r.get(k) or "" for k in DEDUP_KEY))

    OUTPUT_CSV.parent.mkdir(exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, restval="")
        writer.writeheader()
        writer.writerows(
            {
                col: ("" if row.get(col) is None else row.get(col))
                for col in OUTPUT_COLUMNS
            }
            for row in rows
        )
    logger.info(f"Saved {len(rows)} rows to {OUTPUT_CSV}")
    logger.info("HDX Scraper Ebola Bundibugyo completed!")


if __name__ == "__main__":
    facade(
        main,
        user_agent_config_yaml=str(Path.home() / ".useragents.yaml"),
        user_agent_lookup=lookup,
        project_config_yaml=str(
            Path(__file__).parent / "config" / "project_configuration.yaml"
        ),
    )
