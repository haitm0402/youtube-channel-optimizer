"""TOML settings with paths relative to the configuration file, never cwd."""
from dataclasses import dataclass
from pathlib import Path
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    project_name: str = "YouTube Channel Optimizer"
    ai_provider: str = "unconfigured"
    ai_model: str | None = None
    prompts_dir: Path = PROJECT_ROOT / "prompts"
    exports_dir: Path = PROJECT_ROOT / "exports"

    def __post_init__(self) -> None:
        for name in ("project_name", "ai_provider"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.ai_model is not None and (not isinstance(self.ai_model, str) or not self.ai_model.strip()):
            raise ValueError("ai_model must be a non-empty string or None")
        for name in ("prompts_dir", "exports_dir"):
            if not isinstance(getattr(self, name), Path):
                raise ValueError(f"{name} must be a pathlib.Path")


def load_settings(path: Path | str | None = None) -> Settings:
    config_path = Path(path) if path is not None else PROJECT_ROOT / "config" / "default.toml"
    config_path = config_path.resolve()
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    allowed = {"project_name", "ai_provider", "ai_model", "prompts_dir", "exports_dir"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
    for name in ("prompts_dir", "exports_dir"):
        if name in data:
            if not isinstance(data[name], str) or not data[name].strip():
                raise ValueError(f"{name} must be a non-empty path string")
            data[name] = (config_path.parent / Path(data[name])).resolve()
    return Settings(**data)
