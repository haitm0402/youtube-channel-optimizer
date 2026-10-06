"""Configuration diagnostic and explicit offline demo; no external API calls."""
import argparse
from dataclasses import replace
from pathlib import Path
import json
import sys
from config import load_settings
from core.ai_services import CompetitorAnalysisService, ChannelNameService, ChannelPackageService
from core.errors import ApplicationError
from core.prompts import PromptLoader
from models import ChannelProfile, CompetitorInput, TargetAudience
from services.providers import create_text_generator
from services.manual_cli import run_manual
from services.json_sessions import JsonSessionStore
from core.channel_library import ChannelLibrary
from utils.manual_export import export_manual_profile
from utils.json_io import write_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual AI bridge, configuration check, or legacy offline mock demo")
    parser.add_argument("--config", help="Path to an optional TOML configuration")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--manual", action="store_true", help="Run the text-only V1 manual prompt/paste workflow")
    parser.add_argument("--input-json", help="UTF-8 file with competitor input for --manual")
    mode.add_argument("--mock-demo", action="store_true", help="Run analysis and 12 names using fixed mock data")
    mode.add_argument("--sessions", action="store_true", help="List saved active channel projects")
    mode.add_argument("--archive", metavar="SESSION_ID", help="Archive a project without deleting its file")
    mode.add_argument("--export-session", metavar="SESSION_ID", help="Export a completed active or archived project")
    mode.add_argument("--view-session", metavar="SESSION_ID", help="View saved project data without changing it")
    start = parser.add_mutually_exclusive_group()
    start.add_argument("--new", action="store_true", help="Start a new manual session (also the default for --manual)")
    start.add_argument("--resume", metavar="SESSION_ID", help="Resume a saved manual session")
    parser.add_argument("--archived", action="store_true", help="List archived projects with --sessions")
    parser.add_argument("--display-name", help="Human-readable label for a new project")
    parser.add_argument("--select-name", help="Generate/export a mock package for an exact suggested name")
    args = parser.parse_args()
    if args.select_name is not None and not args.mock_demo:
        parser.error("--select-name requires --mock-demo")
    if args.input_json is not None and not args.manual:
        parser.error("--input-json requires --manual")
    if (args.new or args.resume is not None) and not args.manual:
        parser.error("--new and --resume require --manual")
    if args.archived and not args.sessions:
        parser.error("--archived requires --sessions")
    if args.display_name is not None and (not args.manual or args.resume is not None):
        parser.error("--display-name is only for a new manual session")
    if args.resume is not None and args.input_json is not None:
        parser.error("--resume uses saved input; do not supply --input-json")
    try:
        settings = load_settings(args.config)
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
        library = ChannelLibrary(JsonSessionStore(settings.data_dir))
        if args.sessions:
            projects = library.list_projects(archived=args.archived)
            print(json.dumps([dict(session_id=item.session_id, display_name=item.display_name,
                                   competitor_url=item.competitor_url, reference_artist=item.reference_artist,
                                   target_market=item.target_market, target_language=item.target_language,
                                   selected_channel_name=item.selected_channel_name, state=item.state.value,
                                   status=item.status, created_at=item.created_at, updated_at=item.updated_at)
                              for item in projects], ensure_ascii=False, indent=2))
            return
        if args.archive is not None:
            session = library.archive_session(args.archive)
            print(f"Session archived: {session.session_id}")
            return
        if args.export_session is not None:
            print(f"Text channel package exported: {export_manual_profile(library.load_session(args.export_session), settings.exports_dir)}")
            return
        if args.view_session is not None:
            print(json.dumps(library.load_session(args.view_session).to_dict(), ensure_ascii=False, indent=2))
            return
        if not settings.prompts_dir.is_dir():
            parser.error(f"Prompt directory does not exist: {settings.prompts_dir}")
        if args.manual:
            for stream in (sys.stdin, sys.stdout, sys.stderr):
                if hasattr(stream, "reconfigure"):
                    stream.reconfigure(encoding="utf-8")
            competitor = None
            if args.input_json is not None:
                data = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
                competitor = CompetitorInput.from_v1_dict(data)
            run_manual(settings, competitor=competitor, resume_id=args.resume, display_name=args.display_name)
            return
        if not args.mock_demo:
            print(f"Configuration valid. AI provider: {settings.ai_provider}")
            print("Phase 4 V1: use --manual --new, --manual --resume ID, or --sessions; no AI provider required.")
            return
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        provider = create_text_generator(replace(settings, ai_provider="mock"))
        loader = PromptLoader(settings.prompts_dir)
        competitor = CompetitorInput("https://www.youtube.com/@example-music", "demo-avatar.png",
                                     "Playlist nhạc Việt acoustic cho buổi tối.",
                                     TargetAudience(market="Việt Nam", language="Tiếng Việt"))
        analysis = CompetitorAnalysisService(provider, loader).analyze(competitor)
        names = ChannelNameService(provider, loader).generate(analysis)
        print("OFFLINE MOCK DEMO: fixed fixtures; no competitor data retrieved.")
        print(json.dumps({"analysis": analysis.to_ai_dict(),
                          "names": [{"name": item.name, "category": item.category.value,
                                     "short_reason": item.short_reason, "score": item.score}
                                    for item in names.names],
                          "best_recommendation": names.best_recommendation}, ensure_ascii=False, indent=2))
        if args.select_name is None:
            print("Choose a suggested name, then rerun with --mock-demo --select-name NAME.")
            return
        package = ChannelPackageService(provider, loader).generate(analysis, names, args.select_name)
        profile = ChannelProfile(competitor, analysis, args.select_name, package)
        destination = settings.exports_dir / "channel_profile.json"
        write_profile(profile, destination)
        print(f"Mock profile exported: {destination}")
    except (EOFError, KeyboardInterrupt):
        parser.exit(1, "\nManual workflow cancelled; saved transitions are preserved for --manual --resume; incomplete session was not exported.\n")
    except (ApplicationError, ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
