"""Display routing and action delegation, testable without a Tk display."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from config import Settings
from core.channel_library import ChannelLibrary
from core.channel_profiles import ChannelProfileManager
from core.contracts import SessionStore
from core.errors import WorkflowStateError
from core.manual import ManualAIBridge, ManualPromptService
from core.prompts import PromptLoader
from models import CompetitorInput, WorkflowSession, WorkflowState
from services.json_sessions import JsonSessionStore
from services.json_channel_profiles import JsonChannelProfileStore
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
        self.profile_manager = ChannelProfileManager(JsonChannelProfileStore(settings.data_dir), settings.exports_dir)
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


    def list_channel_profiles(self, *, archived: bool = False):
        return self.profile_manager.list_profiles(archived=archived)

    def load_channel_profile(self, profile_id: str):
        return self.profile_manager.load_profile(profile_id)

    def create_channel_profile(self, **values):
        return self.profile_manager.create_profile(**values)

    def update_channel_profile(self, profile_id: str, **changes):
        return self.profile_manager.update_profile(profile_id, **changes)

    def create_profile_from_current_project(self):
        return self.profile_manager.create_from_session(self.session)

    def archive_channel_profile(self, profile_id: str):
        return self.profile_manager.archive_profile(profile_id)

    def restore_channel_profile(self, profile_id: str):
        return self.profile_manager.restore_profile(profile_id)

    def export_channel_profile(self, profile_id: str) -> Path:
        return self.profile_manager.export_profile(profile_id)
