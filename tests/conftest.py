from pathlib import Path

import pytest
from hdx.api.configuration import Configuration
from hdx.utilities.useragent import UserAgent


@pytest.fixture(scope="session")
def fixtures_dir():
    return Path("tests") / "fixtures"


@pytest.fixture(scope="session")
def input_dir(fixtures_dir):
    return fixtures_dir / "input"


@pytest.fixture(scope="session")
def config_dir():
    return Path("src") / "hdx" / "scraper" / "ebola_bundibugyo" / "config"


@pytest.fixture(scope="session")
def configuration(config_dir):
    UserAgent.set_global("test")
    Configuration._create(
        hdx_read_only=True,
        hdx_site="prod",
        project_config_yaml=str(config_dir / "project_configuration.yaml"),
    )
    return Configuration.read()
