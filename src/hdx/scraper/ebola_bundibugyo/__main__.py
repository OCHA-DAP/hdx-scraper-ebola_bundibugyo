import logging
import re
import tempfile
from datetime import date
from os.path import expanduser, join
from pathlib import Path

import pandas as pd
from hdx.data.dataset import Dataset
from hdx.facades.simple import facade
from hdx.utilities.easy_logging import setup_logging

from ._version import __version__

setup_logging()
logger = logging.getLogger(__name__)

lookup = "hdx-scraper-ebola_bundibugyo"
DATASET_NAME = "republique-democratique-du-congo-cas-et-deces-d-ebola"
SHEET_NAME = "Data"
OUTPUT_CSV = Path("saved_data") / "combined_ebola_data.csv"

FRENCH_MONTHS = {
    "janvier": 1,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
}


def parse_french_date(description: str) -> str | None:
    match = re.search(
        r"(?:à la date du|au)\s+(\d{1,2})\s+(\w+)\s+(\d{4})",
        description,
        re.IGNORECASE,
    )
    if not match:
        return None
    day, month_fr, year = match.group(1), match.group(2).lower(), match.group(3)
    month = FRENCH_MONTHS.get(month_fr)
    if month is None:
        return None
    return date(int(year), month, int(day)).isoformat()


def main() -> None:
    logger.info(f"##### {lookup} version {__version__} ####")

    dataset = Dataset.read_from_hdx(DATASET_NAME)
    resources = dataset.get_resources()

    dfs = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        for resource in resources:
            if resource.get_file_type() != "xlsx":
                continue

            description = resource.get("description", "")
            as_of = parse_french_date(description)
            if as_of is None:
                logger.warning(
                    f"Could not parse date from description: {description!r}"
                )

            logger.info(f"Downloading {resource['name']} (AsOf: {as_of})")
            _, filepath = resource.download(folder=tmp_dir)

            try:
                df = pd.read_excel(filepath, sheet_name=SHEET_NAME)
            except Exception as e:
                logger.warning(
                    f"Could not read sheet '{SHEET_NAME}' from {resource['name']}: {e}"
                )
                continue

            df["AsOf"] = as_of
            dfs.append(df)

    if not dfs:
        logger.warning("No xlsx data found!")
        return

    combined = pd.concat(dfs, ignore_index=True)
    OUTPUT_CSV.parent.mkdir(exist_ok=True)
    combined.to_csv(OUTPUT_CSV, index=False)
    logger.info(f"Saved {len(combined)} rows to {OUTPUT_CSV}")
    logger.info("HDX Scraper Ebola Bundibugyo completed!")


if __name__ == "__main__":
    facade(
        main,
        user_agent_config_yaml=join(expanduser("~"), ".useragents.yaml"),
        user_agent_lookup=lookup,
    )
