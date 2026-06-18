import logging
from os.path import expanduser, join

from hdx.api.configuration import Configuration
from hdx.facades.infer_arguments import facade
from hdx.utilities.downloader import Download
from hdx.utilities.path import (
    script_dir_plus_file,
    temp_dir,
)
from hdx.utilities.retriever import Retrieve

from ._version import __version__
from .pipeline import _UPDATED_BY_SCRIPT, Pipeline

logger = logging.getLogger(__name__)

lookup = "hdx-scraper-ebola_bundibugyo"


def main(
    save: bool = False,
    use_saved: bool = False,
) -> None:
    """Download DRC Ebola data from INRB-UMIE and publish to HDX."""
    logger.info(f"##### {lookup} version {__version__} ####")

    configuration = Configuration.read()

    with temp_dir(folder=lookup) as tempdir:
        with Download() as downloader:
            retriever = Retrieve(
                downloader=downloader,
                fallback_dir=tempdir,
                saved_dir=tempdir,
                temp_dir=tempdir,
                save=save,
                use_saved=use_saved,
            )
            pipeline = Pipeline(configuration, retriever)
            rows = pipeline.run()

        if not rows:
            logger.warning("No data found!")
            return

        logger.info(f"Generating HDX dataset from {len(rows)} rows")
        dataset = pipeline.generate_dataset(tempdir, rows)
        dataset.update_from_yaml(
            script_dir_plus_file(join("config", "hdx_dataset_static.yaml"), main)
        )
        logger.info(f"Updating {dataset['name']}")
        dataset.create_in_hdx(
            remove_additional_resources=True,
            match_resource_order=False,
            updated_by_script=_UPDATED_BY_SCRIPT,
        )

    logger.info("HDX Scraper Ebola Bundibugyo completed!")


if __name__ == "__main__":
    facade(
        main,
        user_agent_config_yaml=join(expanduser("~"), ".useragents.yaml"),
        user_agent_lookup=lookup,
        project_config_yaml=script_dir_plus_file(
            join("config", "project_configuration.yaml"), main
        ),
    )
