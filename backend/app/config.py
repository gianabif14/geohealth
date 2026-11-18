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

    # Sumatera Selatan bounding box dengan margin 0.3 derajat untuk daerah perbatasan
    bbox_min_lat: float = -5.20
    bbox_max_lat: float = -1.40
    bbox_min_lon: float = 101.80
    bbox_max_lon: float = 106.40


settings = Settings()
