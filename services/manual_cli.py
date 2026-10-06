"""Resumable manual console bridge; users transfer prompts/JSON themselves."""
from pathlib import Path
from config import Settings
from core.contracts import SessionStore
from core.errors import ApplicationError, SessionStoreError
from core.manual import ManualAIBridge, ManualPromptService
from core.prompts import PromptLoader
from models import CompetitorInput, WorkflowState
from services.json_sessions import JsonSessionStore
from utils.manual_export import export_manual_profile

END_MARKER = "END_JSON"


def _read_pasted_json() -> str:
    print(f"Paste the JSON response. Finish with {END_MARKER} on its own line.")
    lines = []
    while True:
        line = input()
        if line == END_MARKER:
            return "\n".join(lines)
        lines.append(line)


def _import_response(importer):
    while True:
        response = _read_pasted_json()
        try:
            return importer(response)
        except SessionStoreError:
            # A storage failure is not an invalid AI response; stop without advancing state.
            raise
        except (ApplicationError, ValueError) as exc:
            print(f"Response rejected: {exc}. Paste a corrected JSON response.")


def run_manual(settings: Settings, *, competitor: CompetitorInput | None = None,
               resume_id: str | None = None, display_name: str | None = None,
               store: SessionStore | None = None) -> Path:
    print("Manual AI workflow: this application makes no AI or YouTube requests.")
    prompts = ManualPromptService(PromptLoader(settings.prompts_dir))
    store = store if store is not None else JsonSessionStore(settings.data_dir)
    if resume_id is not None:
        if competitor is not None or display_name is not None:
            raise ValueError("Resume uses stored input and display name; do not supply new ones")
        bridge = ManualAIBridge.load_session(resume_id, prompts, store)
    else:
        if competitor is None:
            url = input("Competitor YouTube URL: ")
            description = input("Competitor description (one line; use --input-json for multiline text): ")
            competitor = CompetitorInput(
                competitor_url=url, competitor_description=description,
                target_artist=input("Target artist (optional): ") or None,
                target_market=input("Target market (optional): ") or None,
                target_language=input("Target language (optional): ") or None,
            )
        bridge = ManualAIBridge(competitor, prompts, store=store, display_name=display_name)
    print(f"Session ID: {bridge.session.session_id}")
    print(f"Current state: {bridge.session.state.value}. Progress is saved after each successful transition.")
    while bridge.session.state != WorkflowState.COMPLETE:
        state = bridge.session.state
        if state in {WorkflowState.INPUT, WorkflowState.WAITING_FOR_ANALYSIS}:
            generator, importer = bridge.generate_analysis_prompt, bridge.import_analysis
        elif state in {WorkflowState.ANALYSIS_READY, WorkflowState.WAITING_FOR_NAMES}:
            generator, importer = bridge.generate_names_prompt, bridge.import_names
        elif state in {WorkflowState.NAMES_READY, WorkflowState.NAME_SELECTED}:
            if state == WorkflowState.NAMES_READY:
                for index, item in enumerate(bridge.session.names.names, start=1):
                    print(f"{index}. {item.name} ({item.category.value}, score {item.score})")
                print(f"Recommendation: {bridge.session.names.best_recommendation}")
                while True:
                    selected = input("Enter the exact suggested channel name to select: ")
                    try:
                        bridge.select_name(selected)
                        break
                    except ValueError as exc:
                        print(f"Selection rejected: {exc}")
            generator, importer = bridge.generate_package_prompt, bridge.import_package
        else:  # WAITING_FOR_PACKAGE
            generator, importer = bridge.generate_package_prompt, bridge.import_package
        print("Copy this prompt into ChatGPT/Codex manually:")
        print(generator())  # Waiting states return the exact saved pending prompt.
        _import_response(importer)
    destination = export_manual_profile(bridge.session, settings.exports_dir)
    print(f"Text channel package exported: {destination}")
    return destination
