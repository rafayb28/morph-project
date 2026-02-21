from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    camera_index: int = 0
    yolo_model: str = "yolov8n.pt"
    confidence_threshold: float = 0.45
    detection_interval: float = 0.1
    jpeg_quality: int = 80
    frame_width: int = 1280
    frame_height: int = 720
    max_history: int = 50

    model_config = {"env_file": str(PROJECT_ROOT / ".env"), "env_file_encoding": "utf-8"}


settings = Settings()
