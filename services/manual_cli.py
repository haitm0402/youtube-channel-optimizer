"""Console-only manual bridge. Users transfer prompts/JSON themselves."""
from pathlib import Path
from config import Settings
from core.errors import ApplicationError
from core.manual import ManualAIBridge, ManualPromptService
from core.prompts import PromptLoader
from models import CompetitorInput
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
        except (ApplicationError, ValueError) as exc:
            print(f"Response rejected: {exc}. Paste a corrected JSON response.")


def run_manual(settings: Settings, *, competitor: CompetitorInput | None = None) -> Path:
    print("Manual AI workflow: this application makes no AI or YouTube requests.")
    if competitor is None:
        url = input("Competitor YouTube URL: ")
        description = input("Competitor description (one line; use --input-json for multiline text): ")
        competitor = CompetitorInput(
            competitor_url=url, competitor_description=description,
            target_artist=input("Target artist (optional): ") or None,
            target_market=input("Target market (optional): ") or None,
            target_language=input("Target language (optional): ") or None,
        )
    bridge = ManualAIBridge(competitor, ManualPromptService(PromptLoader(settings.prompts_dir)))
    for prompt_generator, response_importer in (
        (bridge.generate_analysis_prompt, bridge.import_analysis),
        (bridge.generate_names_prompt, bridge.import_names),
    ):
        print("Copy this prompt into ChatGPT/Codex manually:")
        print(prompt_generator())
        _import_response(response_importer)
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
    print("Copy this prompt into ChatGPT/Codex manually:")
    print(bridge.generate_package_prompt())
    _import_response(bridge.import_package)
    destination = export_manual_profile(bridge.session, settings.exports_dir)
    print(f"Text channel package exported: {destination}")
    return destination
