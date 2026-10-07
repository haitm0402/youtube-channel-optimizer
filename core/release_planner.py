"""Release Planner service for multi-channel publishing operations."""
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
import csv
from pathlib import Path
from zoneinfo import ZoneInfo

from models.release_planner import ReleaseChannel, ReleaseItem, ReleasePlan, ReleaseStatus
from models.session_metadata import next_timestamp
from services.json_release_planner import JsonReleasePlannerStore
from utils.manual_export import channel_folder_name


@dataclass(frozen=True)
class ReleaseRow:
    release_id: str
    channel_id: str
    channel_name: str
    song_title: str
    publish_date: str
    publish_time: str
    timezone: str
    vietnam_time: str
    readiness: str
    status: str
    target_market: str | None


@dataclass(frozen=True)
class PlannerSummary:
    today: int
    next_7_days: int
    missing_assets: int
    ready: int
    scheduled: int


WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class ReleasePlannerManager:
    def __init__(self, store: JsonReleasePlannerStore, exports_dir: Path | str):
        self.store = store
        self.exports_dir = Path(exports_dir).resolve()

    def load_plan(self) -> ReleasePlan:
        return self.store.load_plan()

    def _save(self, current: ReleasePlan, *, channels=None, releases=None) -> ReleasePlan:
        updated = ReleasePlan(
            channels=list(current.channels if channels is None else channels),
            releases=list(current.releases if releases is None else releases),
            revision=current.revision + 1,
            created_at=current.created_at,
            updated_at=next_timestamp(current.updated_at),
        )
        self.store.save_plan(updated, expected_revision=current.revision)
        return updated

    def list_channels(self, *, archived: bool = False) -> list[ReleaseChannel]:
        plan = self.load_plan()
        return sorted(
            [item for item in plan.channels if item.archived == archived],
            key=lambda item: item.name.casefold(),
        )

    def get_channel(self, channel_id: str) -> ReleaseChannel:
        plan = self.load_plan()
        for item in plan.channels:
            if item.channel_id == channel_id:
                return item
        raise ValueError("Channel schedule not found")

    def add_channel(self, *, name: str, target_market: str | None = None,
                    timezone: str = "Asia/Ho_Chi_Minh", default_time: str = "20:00",
                    release_days: list[int] | None = None, notes: str | None = None) -> ReleaseChannel:
        plan = self.load_plan()
        if any(item.name.strip().casefold() == name.strip().casefold() and not item.archived for item in plan.channels):
            raise ValueError("An active release-planner channel with this name already exists")
        channel = ReleaseChannel(
            name=name, target_market=target_market, timezone=timezone,
            default_time=default_time, release_days=release_days or [0, 1, 2, 3, 4, 5, 6],
            notes=notes,
        )
        self._save(plan, channels=[*plan.channels, channel])
        return channel

    def update_channel(self, channel_id: str, **changes) -> ReleaseChannel:
        allowed = {"name", "target_market", "timezone", "default_time", "release_days", "notes"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unknown channel fields: {', '.join(sorted(unknown))}")
        plan = self.load_plan()
        channels = []
        result = None
        for item in plan.channels:
            if item.channel_id == channel_id:
                if item.archived:
                    raise ValueError("Archived planner channels are read-only")
                result = replace(item, **changes, updated_at=next_timestamp(item.updated_at))
                channels.append(result)
            else:
                channels.append(item)
        if result is None:
            raise ValueError("Channel schedule not found")
        if any(x.channel_id != channel_id and not x.archived and x.name.strip().casefold() == result.name.strip().casefold() for x in channels):
            raise ValueError("An active release-planner channel with this name already exists")
        self._save(plan, channels=channels)
        return result

    def archive_channel(self, channel_id: str) -> ReleaseChannel:
        plan = self.load_plan()
        channels, result = [], None
        for item in plan.channels:
            if item.channel_id == channel_id:
                result = item if item.archived else replace(item, archived=True, updated_at=next_timestamp(item.updated_at))
                channels.append(result)
            else:
                channels.append(item)
        if result is None:
            raise ValueError("Channel schedule not found")
        if not result.archived:
            raise AssertionError("archive transition failed")
        if result == next((x for x in plan.channels if x.channel_id == channel_id), None):
            return result
        self._save(plan, channels=channels)
        return result

    def restore_channel(self, channel_id: str) -> ReleaseChannel:
        plan = self.load_plan()
        channels, result = [], None
        for item in plan.channels:
            if item.channel_id == channel_id:
                if not item.archived:
                    return item
                if any(x.channel_id != channel_id and not x.archived and x.name.strip().casefold() == item.name.strip().casefold() for x in plan.channels):
                    raise ValueError("Restore would duplicate an active channel name")
                result = replace(item, archived=False, updated_at=next_timestamp(item.updated_at))
                channels.append(result)
            else:
                channels.append(item)
        if result is None:
            raise ValueError("Channel schedule not found")
        self._save(plan, channels=channels)
        return result

    def suggest_next_slot(self, channel_id: str, *, start_date: str | None = None) -> tuple[str, str, str]:
        plan = self.load_plan()
        channel = next((item for item in plan.channels if item.channel_id == channel_id), None)
        if channel is None:
            raise ValueError("Channel schedule not found")
        if channel.archived:
            raise ValueError("Archived planner channels cannot receive new releases")
        if start_date is None:
            current = datetime.now(ZoneInfo(channel.timezone)).date()
        else:
            current = date.fromisoformat(start_date)
        occupied = {
            (item.publish_date, item.publish_time) for item in plan.releases
            if item.channel_id == channel_id and not item.archived
        }
        allowed = set(channel.release_days)
        for offset in range(0, 370):
            candidate = current + timedelta(days=offset)
            slot = (candidate.isoformat(), channel.default_time)
            if candidate.weekday() in allowed and slot not in occupied:
                return slot[0], slot[1], channel.timezone
        raise ValueError("No free release slot found in the next 370 days")

    def add_release(self, *, channel_id: str, song_title: str, publish_date: str,
                    publish_time: str, timezone: str, status: str = "PLANNED",
                    video_title: str | None = None, audio_ready: bool = False,
                    thumbnail_ready: bool = False, video_ready: bool = False,
                    seo_ready: bool = False, youtube_url: str | None = None,
                    notes: str | None = None) -> ReleaseItem:
        plan = self.load_plan()
        channel = next((item for item in plan.channels if item.channel_id == channel_id), None)
        if channel is None or channel.archived:
            raise ValueError("Select an active planner channel")
        release = ReleaseItem(
            channel_id=channel_id, song_title=song_title, video_title=video_title,
            publish_date=publish_date, publish_time=publish_time, timezone=timezone,
            status=status, audio_ready=audio_ready, thumbnail_ready=thumbnail_ready,
            video_ready=video_ready, seo_ready=seo_ready, youtube_url=youtube_url, notes=notes,
        )
        self._assert_no_duplicate(plan, release)
        self._save(plan, releases=[*plan.releases, release])
        return release

    def get_release(self, release_id: str) -> ReleaseItem:
        plan = self.load_plan()
        for item in plan.releases:
            if item.release_id == release_id:
                return item
        raise ValueError("Release not found")

    def update_release(self, release_id: str, **changes) -> ReleaseItem:
        allowed = {
            "channel_id", "song_title", "video_title", "publish_date", "publish_time",
            "timezone", "status", "audio_ready", "thumbnail_ready", "video_ready",
            "seo_ready", "youtube_url", "notes",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unknown release fields: {', '.join(sorted(unknown))}")
        plan = self.load_plan()
        releases, result = [], None
        for item in plan.releases:
            if item.release_id == release_id:
                if item.archived:
                    raise ValueError("Archived releases are read-only")
                result = replace(item, **changes, updated_at=next_timestamp(item.updated_at))
                releases.append(result)
            else:
                releases.append(item)
        if result is None:
            raise ValueError("Release not found")
        channel = next((x for x in plan.channels if x.channel_id == result.channel_id), None)
        if channel is None:
            raise ValueError("Selected channel does not exist")
        self._assert_no_duplicate(plan, result, ignore_release_id=release_id)
        self._save(plan, releases=releases)
        return result

    def mark_published(self, release_id: str, youtube_url: str | None = None) -> ReleaseItem:
        return self.update_release(release_id, status=ReleaseStatus.PUBLISHED.value, youtube_url=youtube_url)

    def archive_release(self, release_id: str) -> ReleaseItem:
        plan = self.load_plan()
        releases, result = [], None
        for item in plan.releases:
            if item.release_id == release_id:
                if item.archived:
                    return item
                result = replace(item, archived=True, updated_at=next_timestamp(item.updated_at))
                releases.append(result)
            else:
                releases.append(item)
        if result is None:
            raise ValueError("Release not found")
        self._save(plan, releases=releases)
        return result

    def _assert_no_duplicate(self, plan: ReleasePlan, candidate: ReleaseItem, ignore_release_id: str | None = None) -> None:
        for item in plan.releases:
            if item.archived or item.release_id == ignore_release_id:
                continue
            if (item.channel_id, item.publish_date, item.publish_time) == (
                candidate.channel_id, candidate.publish_date, candidate.publish_time
            ):
                raise ValueError("This channel already has a release in the same date/time slot")

    @staticmethod
    def vietnam_time(item: ReleaseItem) -> str:
        source = datetime.fromisoformat(f"{item.publish_date}T{item.publish_time}:00").replace(tzinfo=ZoneInfo(item.timezone))
        converted = source.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
        return converted.strftime("%Y-%m-%d %H:%M")

    def list_release_rows(self, *, range_name: str = "Next 7 Days",
                          channel_id: str | None = None, status: str | None = None,
                          include_archived: bool = False, today: date | None = None) -> list[ReleaseRow]:
        plan = self.load_plan()
        today = today or date.today()
        ranges = {
            "Today": (today, today),
            "Next 7 Days": (today, today + timedelta(days=6)),
            "Next 30 Days": (today, today + timedelta(days=29)),
            "All": (None, None),
        }
        if range_name not in ranges:
            raise ValueError("Unknown release date filter")
        start, end = ranges[range_name]
        if status:
            status = ReleaseStatus(status).value
        channel_map = {item.channel_id: item for item in plan.channels}
        rows = []
        for item in plan.releases:
            if item.archived != include_archived:
                continue
            when = date.fromisoformat(item.publish_date)
            if start is not None and not (start <= when <= end):
                continue
            if channel_id and item.channel_id != channel_id:
                continue
            if status and item.status.value != status:
                continue
            channel = channel_map[item.channel_id]
            rows.append(ReleaseRow(
                release_id=item.release_id, channel_id=item.channel_id,
                channel_name=channel.name, song_title=item.song_title,
                publish_date=item.publish_date, publish_time=item.publish_time,
                timezone=item.timezone, vietnam_time=self.vietnam_time(item),
                readiness=item.readiness_label, status=item.status.value,
                target_market=channel.target_market,
            ))
        return sorted(rows, key=lambda row: (row.publish_date, row.publish_time, row.channel_name.casefold()))

    def summary(self, *, today: date | None = None) -> PlannerSummary:
        plan = self.load_plan()
        today = today or date.today()
        active = [item for item in plan.releases if not item.archived]
        next_7 = today + timedelta(days=6)
        return PlannerSummary(
            today=sum(date.fromisoformat(x.publish_date) == today for x in active),
            next_7_days=sum(today <= date.fromisoformat(x.publish_date) <= next_7 for x in active),
            missing_assets=sum(bool(x.missing_assets) and x.status != ReleaseStatus.PUBLISHED for x in active),
            ready=sum(not x.missing_assets and x.status not in {ReleaseStatus.PUBLISHED, ReleaseStatus.SCHEDULED} for x in active),
            scheduled=sum(x.status == ReleaseStatus.SCHEDULED for x in active),
        )

    def export_csv(self) -> Path:
        rows = self.list_release_rows(range_name="All")
        destination_dir = self.exports_dir / "release_planner"
        destination_dir.mkdir(parents=True, exist_ok=True)
        for suffix in range(1000):
            destination = destination_dir / ("release_plan.csv" if suffix == 0 else f"release_plan-{suffix}.csv")
            if not destination.exists():
                break
        else:
            raise FileExistsError("Cannot allocate a fresh release-plan export")
        try:
            with destination.open("x", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Date", "Time", "Vietnam Time", "Channel", "Song", "Market", "Timezone", "Readiness", "Status"])
                for row in rows:
                    writer.writerow([
                        row.publish_date, row.publish_time, row.vietnam_time, row.channel_name,
                        row.song_title, row.target_market or "", row.timezone, row.readiness, row.status,
                    ])
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return destination
