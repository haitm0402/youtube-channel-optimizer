"""Export text-only completed workflows into fresh folders, safe on Windows."""
import json
from pathlib import Path
import re
import shutil
import unicodedata
from models import WorkflowSession

_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in "123456789¹²³"
}


def channel_folder_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Channel name must be non-empty")
    normalized = unicodedata.normalize("NFC", name)
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', '-', normalized)
    safe = re.sub(r'\s+', ' ', safe).strip(' .')[:80].rstrip(' .') or 'channel'
    if safe.split('.', 1)[0].rstrip().upper() in _RESERVED:
        safe = '_' + safe
    return safe


def export_manual_profile(session: WorkflowSession, exports_dir: Path | str) -> Path:
    profile = session.to_profile_dict()  # Validate everything before writing any file.
    root = Path(exports_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = channel_folder_name(session.selected_name)
    for suffix in range(1000):
        destination = root / (name if suffix == 0 else f"{name}-{suffix}")
        try:
            destination.mkdir()  # Atomic allocation; do not overwrite existing exports or symlinks.
            break
        except FileExistsError:
            continue
    else:
        raise FileExistsError("Cannot allocate a fresh channel export folder")
    text_files = {
        "channel_description.txt": "channel_description", "channel_keywords.txt": "channel_keywords",
        "video_keywords.txt": "video_core_keywords", "video_tags.txt": "video_tags", "hashtags.txt": "hashtags",
        "title_templates.txt": "title_templates", "thumbnail_direction.txt": "thumbnail_direction",
        "banner_direction.txt": "banner_direction",
    }
    try:
        (destination / "channel_profile.json").write_text(
            json.dumps(profile, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        for filename, field in text_files.items():
            value = profile["package"][field]
            text = "\n".join(value) if isinstance(value, list) else value
            (destination / filename).write_text(text + "\n", encoding="utf-8")
    except Exception:
        # Only this function's freshly allocated folder is removed after an incomplete write.
        shutil.rmtree(destination)
        raise
    return destination
