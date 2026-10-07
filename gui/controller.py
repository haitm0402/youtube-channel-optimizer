"""Display routing and action delegation, testable without a Tk display."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from config import Settings
from core.channel_library import ChannelLibrary
from core.release_planner import ReleasePlannerManager
from core.contracts import SessionStore
from core.errors import WorkflowStateError
from core.manual import ManualAIBridge, ManualPromptService
from core.prompts import PromptLoader
from models import CompetitorInput, WorkflowSession, WorkflowState
from services.json_sessions import JsonSessionStore
from services.json_release_planner import JsonReleasePlannerStore
from utils.manual_export import export_manual_profile


class ProjectFilter(str, Enum):
    ACTIVE = "Active"
    COMPLETED = "Completed"
    ARCHIVED = "Archived"


class EditorScreen(str, Enum):
    ANALYSIS = "analysis"
    NAMES_PROMPT = "names_prompt"
    NAME_SELECTION = "name_selection"
    PACKAGE_PROMPT = "package_prompt"
    PACKAGE = "package"


_SCREEN = {
    WorkflowState.INPUT: EditorScreen.ANALYSIS,
    WorkflowState.WAITING_FOR_ANALYSIS: EditorScreen.ANALYSIS,
    WorkflowState.ANALYSIS_READY: EditorScreen.NAMES_PROMPT,
    WorkflowState.WAITING_FOR_NAMES: EditorScreen.NAMES_PROMPT,
    WorkflowState.NAMES_READY: EditorScreen.NAME_SELECTION,
    WorkflowState.NAME_SELECTED: EditorScreen.PACKAGE_PROMPT,
    WorkflowState.WAITING_FOR_PACKAGE: EditorScreen.PACKAGE_PROMPT,
    WorkflowState.COMPLETE: EditorScreen.PACKAGE,
}


def screen_for_state(state: WorkflowState) -> EditorScreen:
    return _SCREEN[WorkflowState(state)]


@dataclass(frozen=True)
class PackageSection:
    field: str
    label: str
    text: str


_PACKAGE_LABELS = (
    ("channel_positioning", "Channel Positioning"), ("channel_description", "Channel Description"),
    ("channel_keywords", "Channel Keywords"), ("video_core_keywords", "Video Keywords"),
    ("video_tags", "Video Tags"), ("hashtags", "Hashtags"), ("title_templates", "Title Templates"),
    ("thumbnail_direction", "Thumbnail Direction"), ("banner_direction", "Banner Direction"), ("slogan", "Slogan"),
)


def package_sections(session: WorkflowSession) -> list[PackageSection]:
    if session.state != WorkflowState.COMPLETE:
        raise WorkflowStateError("Complete the package before viewing its sections")
    return [PackageSection(field, label, "\n".join(value) if isinstance(value, list) else value)
            for field, label in _PACKAGE_LABELS for value in [getattr(session.package, field)]]


class GUIController:
    def __init__(self, settings: Settings, store: SessionStore | None = None):
        self.settings = settings
        self.store = store if store is not None else JsonSessionStore(settings.data_dir)
        self.library = ChannelLibrary(self.store)
        self.release_planner = ReleasePlannerManager(JsonReleasePlannerStore(settings.data_dir), settings.exports_dir)
        self.prompts = ManualPromptService(PromptLoader(settings.prompts_dir))
        self._bridge: ManualAIBridge | None = None
        self._archived: WorkflowSession | None = None

    @property
    def session(self) -> WorkflowSession:
        if self._archived is not None:
            return self._archived
        if self._bridge is None:
            raise WorkflowStateError("Open or create a project first")
        return self._bridge.session

    def list_projects(self, filter_name: ProjectFilter = ProjectFilter.ACTIVE):
        filter_name = ProjectFilter(filter_name)
        projects = self.library.list_projects(archived=filter_name == ProjectFilter.ARCHIVED)
        if filter_name == ProjectFilter.ARCHIVED:
            return projects
        return [item for item in projects if (item.state == WorkflowState.COMPLETE) ==
                (filter_name == ProjectFilter.COMPLETED)]

    def create_project(self, *, project_name: str, competitor_url: str, competitor_description: str,
                       target_artist: str | None = None, target_market: str | None = None,
                       target_language: str | None = None) -> WorkflowSession:
        if not isinstance(project_name, str) or not project_name.strip():
            raise ValueError("Project Name is required")
        competitor = CompetitorInput(competitor_url=competitor_url, competitor_description=competitor_description,
                                     target_artist=target_artist, target_market=target_market, target_language=target_language)
        value = ManualAIBridge(competitor, self.prompts, store=self.store, display_name=project_name)
        self._bridge, self._archived = value, None
        return self.prepare_screen()

    def open_project(self, session_id: str) -> WorkflowSession:
        saved = self.library.load_session(session_id)
        if saved.archived:
            self._bridge, self._archived = None, saved
            return saved
        self._bridge = ManualAIBridge.load_session(session_id, self.prompts, self.store)
        self._archived = None
        return self.prepare_screen()

    def _editable(self) -> ManualAIBridge:
        if self.session.archived:
            raise WorkflowStateError("Archived projects are read-only")
        return self._bridge

    def prepare_screen(self) -> WorkflowSession:
        if self.session.archived:
            return self.session
        bridge = self._editable()
        generators = {
            WorkflowState.INPUT: bridge.generate_analysis_prompt,
            WorkflowState.ANALYSIS_READY: bridge.generate_names_prompt,
            WorkflowState.NAME_SELECTED: bridge.generate_package_prompt,
        }
        if self.session.state in generators:
            generators[self.session.state]()
        return self.session

    def pending_prompt(self) -> str:
        # This action only retrieves the saved string; it never invokes a renderer or saves.
        if self.session.pending_prompt is None:
            raise WorkflowStateError("This project has no pending prompt")
        return self.session.pending_prompt

    def submit_json(self, text: str) -> WorkflowSession:
        bridge = self._editable()
        importers = {
            WorkflowState.WAITING_FOR_ANALYSIS: bridge.import_analysis,
            WorkflowState.WAITING_FOR_NAMES: bridge.import_names,
            WorkflowState.WAITING_FOR_PACKAGE: bridge.import_package,
        }
        if self.session.state not in importers:
            raise WorkflowStateError("This step does not accept a JSON response")
        importers[self.session.state](text)
        return self.prepare_screen()

    def select_name(self, name: str | None) -> WorkflowSession:
        if not isinstance(name, str) or not name:
            raise ValueError("Please select one channel name")
        self._editable().select_name(name)
        return self.prepare_screen()

    def archive_project(self, session_id: str, *, confirmed: bool) -> bool:
        if confirmed is not True:
            return False
        archived = self.library.archive_session(session_id)
        if self._bridge is not None and self._bridge.session.session_id == session_id:
            self._bridge, self._archived = None, archived
        return True

    def export_project(self) -> Path:
        return export_manual_profile(self.session, self.settings.exports_dir)


    def release_planner_snapshot(self):
        return {
            "channels": self.release_planner.list_channels(),
            "releases": self.release_planner.list_release_rows(range_name="Next 7 Days"),
            "summary": self.release_planner.summary(),
        }

    def list_release_rows(self, **filters):
        return self.release_planner.list_release_rows(**filters)

    def list_release_channels(self, *, archived: bool = False):
        return self.release_planner.list_channels(archived=archived)

    def get_release_channel(self, channel_id: str):
        return self.release_planner.get_channel(channel_id)

    def add_release_channel(self, **values):
        return self.release_planner.add_channel(**values)

    def update_release_channel(self, channel_id: str, **changes):
        return self.release_planner.update_channel(channel_id, **changes)

    def archive_release_channel(self, channel_id: str):
        return self.release_planner.archive_channel(channel_id)

    def restore_release_channel(self, channel_id: str):
        return self.release_planner.restore_channel(channel_id)

    def suggest_next_release_slot(self, channel_id: str, *, start_date: str | None = None):
        return self.release_planner.suggest_next_slot(channel_id, start_date=start_date)

    def add_release(self, **values):
        return self.release_planner.add_release(**values)

    def get_release(self, release_id: str):
        return self.release_planner.get_release(release_id)

    def update_release(self, release_id: str, **changes):
        return self.release_planner.update_release(release_id, **changes)

    def mark_release_published(self, release_id: str, youtube_url: str | None = None):
        return self.release_planner.mark_published(release_id, youtube_url=youtube_url)

    def archive_release(self, release_id: str):
        return self.release_planner.archive_release(release_id)

    def export_release_plan_csv(self) -> Path:
        return self.release_planner.export_csv()
