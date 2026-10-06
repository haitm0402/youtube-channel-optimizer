"""UTF-8 JSON helpers; no implicit platform encoding or working directory."""
import json
from pathlib import Path
from models import ChannelProfile


def write_profile(profile: ChannelProfile, path: Path | str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_profile(path: Path | str) -> ChannelProfile:
    return ChannelProfile.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
