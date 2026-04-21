"""应用配置管理."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API 配置
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_workers: int = Field(default=1, alias="API_WORKERS")
    
    # 模型配置
    model_dir: Path = Field(default=Path("models"), alias="MODEL_DIR")
    svm_model_path: Path = Field(
        default=Path("models/svm_sentiment.pkl"), alias="SVM_MODEL_PATH"
    )
    vlm_model_path: Path = Field(
        default=Path("models/vlm_classifier.pt"), alias="VLM_MODEL_PATH"
    )
    
    # VLM 配置
    vlm_use_local: bool = Field(default=True, alias="VLM_USE_LOCAL")
    vlm_api_key: str = Field(default="", alias="VLM_API_KEY")
    vlm_base_url: str = Field(
        default="https://api.siliconflow.cn/v1", alias="VLM_BASE_URL"
    )
    vlm_model_name: str = Field(
        default="Qwen/Qwen2-VL-7B-Instruct", alias="VLM_MODEL_NAME"
    )
    
    # 训练配置
    batch_size: int = Field(default=32, alias="BATCH_SIZE")
    learning_rate: float = Field(default=1e-4, alias="LEARNING_RATE")
    num_epochs: int = Field(default=10, alias="NUM_EPOCHS")
    device: str = Field(default="auto", alias="DEVICE")

    @property
    def project_root(self) -> Path:
        """项目根目录."""
        return Path(__file__).resolve().parent.parent.parent

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def html_pages_dir(self) -> Path:
        return self.raw_dir / "html_pages"

    @property
    def image_dir(self) -> Path:
        return self.project_root / "image"

    @property
    def configs_dir(self) -> Path:
        return self.project_root / "configs"

    def ensure_dirs(self) -> None:
        """确保所有必要的目录存在."""
        dirs = [
            self.data_dir,
            self.raw_dir,
            self.processed_dir,
            self.reports_dir,
            self.html_pages_dir,
            self.model_dir,
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """获取配置单例."""
    return Settings()
