"""Manual AI bridge: generate prompts and import pasted JSON, never call a provider."""
from dataclasses import replace
import json
from .errors import WorkflowStateError
from .contracts import SessionStore
from models.session_metadata import next_timestamp
from .prompts import PromptLoader, PromptRenderer
from .responses import parse_response
from models import (ChannelNameResult, ChannelPackageV1, CompetitorAnalysis, CompetitorInput,
                    WorkflowSession, WorkflowState)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class ManualPromptService:
    def __init__(self, loader: PromptLoader, renderer: PromptRenderer | None = None):
        self.loader = loader
        self.renderer = renderer if renderer is not None else PromptRenderer()

    def analysis_prompt(self, competitor: CompetitorInput) -> str:
        if not isinstance(competitor, CompetitorInput):
            raise ValueError("competitor must be a CompetitorInput")
        return self.renderer.render(self.loader.load("analyze_competitor.md"), {
            "competitor_json": _json(competitor.to_prompt_dict()),
        })

    def names_prompt(self, analysis: CompetitorAnalysis) -> str:
        if not isinstance(analysis, CompetitorAnalysis):
            raise ValueError("analysis must be a CompetitorAnalysis")
        validated = CompetitorAnalysis.from_ai_dict(analysis.to_ai_dict())
        return self.renderer.render(self.loader.load("generate_names.md"), {
            "analysis_json": _json(validated.to_ai_dict()),
        })

    def package_prompt(self, analysis: CompetitorAnalysis, names: ChannelNameResult,
                       selected_name: str) -> str:
        if not isinstance(analysis, CompetitorAnalysis) or not isinstance(names, ChannelNameResult):
            raise ValueError("analysis and names must be typed analysis/name results")
        validated = CompetitorAnalysis.from_ai_dict(analysis.to_ai_dict())
        validated_names = ChannelNameResult.from_ai_dict(names.to_ai_dict())
        if selected_name not in [item.name for item in validated_names.names]:
            raise ValueError("selected_name must exactly match a suggested name")
        return self.renderer.render(self.loader.load("generate_package_v1.md"), {
            "analysis_json": _json(validated.to_ai_dict()), "selected_name_json": _json(selected_name),
        })


class ManualResponseService:
    def import_analysis(self, pasted_json: str) -> CompetitorAnalysis:
        return parse_response(pasted_json, CompetitorAnalysis.from_ai_dict)

    def import_names(self, pasted_json: str) -> ChannelNameResult:
        return parse_response(pasted_json, ChannelNameResult.from_ai_dict)

    def import_package(self, pasted_json: str) -> ChannelPackageV1:
        return parse_response(pasted_json, ChannelPackageV1.from_dict)


class ManualAIBridge:
    def __init__(self, competitor: CompetitorInput, prompts: ManualPromptService,
                 responses: ManualResponseService | None = None, *,
                 store: SessionStore | None = None, display_name: str | None = None):
        self.prompts = prompts
        self.responses = responses if responses is not None else ManualResponseService()
        self.store = store
        self._session = WorkflowSession(competitor, display_name=display_name)
        if self.store is not None:
            self.store.save_session(self._session)

    @classmethod
    def load_session(cls, session_id: str, prompts: ManualPromptService, store: SessionStore,
                     responses: ManualResponseService | None = None) -> "ManualAIBridge":
        session = store.load_session(session_id)
        if session.archived:
            raise WorkflowStateError("Archived sessions are read-only; use the library to view/export them")
        value = cls.__new__(cls)
        value.prompts = prompts
        value.responses = responses if responses is not None else ManualResponseService()
        value.store = store
        value._session = session
        return value

    def _commit(self, **changes) -> None:
        candidate = replace(self.session, **changes, updated_at=next_timestamp(self.session.updated_at),
                            revision=self.session.revision + 1)
        if self.store is not None:
            self.store.save_session(candidate, expected_revision=self.session.revision)
        self._session = candidate

    @property
    def session(self) -> WorkflowSession:
        return self._session

    def _require(self, *states: WorkflowState) -> None:
        if self.session.archived:
            raise WorkflowStateError("Archived sessions are read-only")
        if self.session.state not in states:
            expected = ", ".join(state.value for state in states)
            raise WorkflowStateError(f"Current state {self.session.state.value}; expected {expected}")

    def generate_analysis_prompt(self) -> str:
        self._require(WorkflowState.INPUT, WorkflowState.WAITING_FOR_ANALYSIS)
        if self.session.state == WorkflowState.WAITING_FOR_ANALYSIS:
            return self.session.pending_prompt
        prompt = self.prompts.analysis_prompt(self.session.competitor)
        self._commit(state=WorkflowState.WAITING_FOR_ANALYSIS, pending_prompt=prompt)
        return prompt

    def import_analysis(self, pasted_json: str) -> CompetitorAnalysis:
        self._require(WorkflowState.WAITING_FOR_ANALYSIS)
        analysis = self.responses.import_analysis(pasted_json)
        self._commit(state=WorkflowState.ANALYSIS_READY, analysis=analysis, pending_prompt=None)
        return analysis

    def generate_names_prompt(self) -> str:
        self._require(WorkflowState.ANALYSIS_READY, WorkflowState.WAITING_FOR_NAMES)
        if self.session.state == WorkflowState.WAITING_FOR_NAMES:
            return self.session.pending_prompt
        prompt = self.prompts.names_prompt(self.session.analysis)
        self._commit(state=WorkflowState.WAITING_FOR_NAMES, pending_prompt=prompt)
        return prompt

    def import_names(self, pasted_json: str) -> ChannelNameResult:
        self._require(WorkflowState.WAITING_FOR_NAMES)
        names = self.responses.import_names(pasted_json)
        self._commit(state=WorkflowState.NAMES_READY, names=names, pending_prompt=None)
        return names

    def select_name(self, selected_name: str) -> None:
        self._require(WorkflowState.NAMES_READY, WorkflowState.NAME_SELECTED)
        self._commit(state=WorkflowState.NAME_SELECTED, selected_name=selected_name)

    def generate_package_prompt(self) -> str:
        self._require(WorkflowState.NAME_SELECTED, WorkflowState.WAITING_FOR_PACKAGE)
        if self.session.state == WorkflowState.WAITING_FOR_PACKAGE:
            return self.session.pending_prompt
        prompt = self.prompts.package_prompt(self.session.analysis, self.session.names, self.session.selected_name)
        self._commit(state=WorkflowState.WAITING_FOR_PACKAGE, pending_prompt=prompt)
        return prompt

    def import_package(self, pasted_json: str) -> ChannelPackageV1:
        self._require(WorkflowState.WAITING_FOR_PACKAGE)
        package = self.responses.import_package(pasted_json)
        self._commit(state=WorkflowState.COMPLETE, package=package, pending_prompt=None)
        return package
