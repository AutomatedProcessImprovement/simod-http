from pathlib import Path

from simod_http.configurations import ApplicationConfiguration

tests_base_dir = Path(__file__).parent


def test_application_configuration():
    config = ApplicationConfiguration(dotenv_path=tests_base_dir / ".env.test")

    assert config.debug is True
    assert config.http.host == "localhost"
    assert config.http.port == 8000
    assert config.http.scheme == "http"

    assert config.storage.path == "./tmp"
    assert config.storage.discovery_expiration_timedelta == 604800
    assert config.storage.cleaning_timedelta == 60

    assert config.logging.level == "info"
    assert config.logging.format == "%(asctime)s \t %(name)s \t %(levelname)s \t %(message)s"

    assert config.mongo.url == "mongodb://localhost:27017/simod"
    assert config.mongo.discoveries_collection == "discoveries"
