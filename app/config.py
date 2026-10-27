"""server-v2 配置：端口、数据目录。mock 服务零外部依赖（无数据库），文件即存储。"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    server_host: str = "0.0.0.0"
    server_port: int = 8200

    # 运行时目录（相对 BASE_DIR）
    upload_dir: str = "data/uploads"
    export_dir: str = "data/exports"
    standards_dir: str = "data/standards"
    sample_dir: str = "data/sample"

    def resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else BASE_DIR / p

    @property
    def uploads_root(self) -> Path:
        return self.resolve(self.upload_dir)

    @property
    def exports_root(self) -> Path:
        return self.resolve(self.export_dir)

    @property
    def standards_root(self) -> Path:
        return self.resolve(self.standards_dir)

    @property
    def data_root(self) -> Path:
        """静态目录挂载根：/files/uploads/... 与 /files/exports/..."""
        return self.resolve("data")


settings = Settings()


def ensure_dirs() -> None:
    for d in (settings.uploads_root, settings.exports_root, settings.standards_root):
        d.mkdir(parents=True, exist_ok=True)
