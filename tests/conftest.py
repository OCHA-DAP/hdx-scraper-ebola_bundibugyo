import pytest
from hdx.api.configuration import Configuration
from hdx.utilities.useragent import UserAgent


@pytest.fixture(scope="session")
def configuration():
    UserAgent.set_global("test")
    Configuration._create(
        hdx_read_only=True,
        hdx_site="prod",
    )
    return Configuration.read()
