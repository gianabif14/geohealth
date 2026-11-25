from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://geohealth:geohealth_dev_pass@127.0.0.1:5432/geohealth"
    firms_map_key: str = ""
    osrm_url: str = "https://router.project-osrm.org"

    # Bounding box cakupan seluruh wilayah Indonesia
    bbox_min_lat: float = -11.10
    bbox_max_lat: float = 6.10
    bbox_min_lon: float = 94.90
    bbox_max_lon: float = 141.10


settings = Settings()
