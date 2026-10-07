"""Atomic local persistence for the Release Planner."""
import json
import os
from pathlib import Path
import tempfile

from core.errors import ReleasePlannerConflictError, ReleasePlannerStoreError
from models.release_planner import ReleasePlan


class JsonReleasePlannerStore:
    def __init__(self, data_dir: Path | str):
        self.path = Path(data_dir).resolve() / "release_planner.json"

    def load_plan(self) -> ReleasePlan:
        if not self.path.exists():
            return ReleasePlan()
        try:
            raw = self.path.read_text(encoding="utf-8")
            def reject_duplicates(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError(f"duplicate key: {key}")
                    result[key] = value
                return result
            def reject_constant(value):
                raise ValueError(f"invalid JSON constant: {value}")
            data = json.loads(raw, object_pairs_hook=reject_duplicates, parse_constant=reject_constant)
            return ReleasePlan.from_dict(data)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            raise ReleasePlannerStoreError(f"Corrupt or incompatible release planner data: {exc}") from exc

    def save_plan(self, plan: ReleasePlan, *, expected_revision: int) -> None:
        if not isinstance(plan, ReleasePlan):
            raise ReleasePlannerStoreError("Expected a ReleasePlan")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ReleasePlannerStoreError("expected_revision must be a non-negative integer")
        try:
            candidate = ReleasePlan.from_dict(plan.to_dict())
            payload = json.dumps(candidate.to_dict(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        except (TypeError, ValueError, KeyError) as exc:
            raise ReleasePlannerStoreError(f"Release plan validation failed: {exc}") from exc

        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                current = self.load_plan()
                if current.revision != expected_revision:
                    raise ReleasePlannerConflictError("Release plan changed in another process; refresh before saving")
            elif expected_revision != 0:
                raise ReleasePlannerConflictError("Release plan changed or was removed; refresh before saving")
            if candidate.revision != expected_revision + 1:
                raise ReleasePlannerStoreError("Updated revision must increase by exactly 1")

            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=".release-planner-", suffix=".tmp", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            temporary = None
        except (ReleasePlannerConflictError, ReleasePlannerStoreError):
            raise
        except OSError as exc:
            raise ReleasePlannerStoreError("Cannot save release planner data") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
