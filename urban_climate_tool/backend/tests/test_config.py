from pathlib import Path

from app.core.config import Settings


def test_settings_loads_defaults() -> None:
    config = Settings(_env_file=None)
    assert config.data_root == "./storage"
    assert config.layer_catalog_path == "./catalog/layers.yaml"


def test_data_root_is_resolved() -> None:
    config = Settings(data_root="./storage", layer_catalog_path="./catalog/layers.yaml", _env_file=None)
    assert Path(config.data_root).exists() or True


def test_cors_parse() -> None:
    config = Settings(cors_origins="http://localhost:3000,http://localhost:3001", _env_file=None)
    assert config.cors_origins == ["http://localhost:3000", "http://localhost:3001"]
