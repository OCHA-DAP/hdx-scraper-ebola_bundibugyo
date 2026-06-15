import logging
import sys
import tempfile
from os import getenv
from pathlib import Path

from hdx.api.configuration import Configuration
from hdx.facades.infer_arguments import facade
from hdx.utilities.downloader import Download
from hdx.utilities.easy_logging import setup_logging
from hdx.utilities.retriever import Retrieve

from ._version import __version__
from .gsheet import write_to_gsheet
from .pipeline import Pipeline

setup_logging()
logger = logging.getLogger(__name__)

lookup = "hdx-scraper-ebola_bundibugyo"


def main(gsheet_auth: str | None = None) -> None:
    """Download DRC Ebola data from INRB-UMIE GitHub repo and write a long-format CSV."""
    logger.info(f"##### {lookup} version {__version__} ####")

    if gsheet_auth is None:
        gsheet_auth = getenv("GSHEET_AUTH")
    if gsheet_auth is None:
        logger.error("No Google sheets authentication supplied!")
        sys.exit(1)

    configuration = Configuration.read()

    with tempfile.TemporaryDirectory() as tmp_dir:
        with Download() as downloader:
            retriever = Retrieve(downloader, tmp_dir, tmp_dir, tmp_dir)
            pipeline = Pipeline(configuration, retriever)
            rows = pipeline.run()

    if not rows:
        logger.warning("No data found!")
        return

    logger.info(f"Saving {len(rows)} rows to Google sheet")
    write_to_gsheet(rows, gsheet_auth, configuration)

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
