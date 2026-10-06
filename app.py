"""Configuration diagnostic and explicit offline demo; no external API calls."""
import argparse
from dataclasses import replace
import json
import sys
from config import load_settings
from core.ai_services import CompetitorAnalysisService, ChannelNameService, ChannelPackageService
from core.errors import ApplicationError
from core.prompts import PromptLoader
from models import ChannelProfile, CompetitorInput, TargetAudience
from services.providers import create_text_generator
from utils.json_io import write_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate configuration or run the offline mock pipeline")
    parser.add_argument("--config", help="Path to an optional TOML configuration")
    parser.add_argument("--mock-demo", action="store_true", help="Run analysis and 12 names using fixed mock data")
    parser.add_argument("--select-name", help="Generate/export a mock package for an exact suggested name")
    args = parser.parse_args()
    if args.select_name is not None and not args.mock_demo:
        parser.error("--select-name requires --mock-demo")
    try:
        settings = load_settings(args.config)
        if not settings.prompts_dir.is_dir():
            parser.error(f"Prompt directory does not exist: {settings.prompts_dir}")
        if not args.mock_demo:
            print(f"Configuration valid. AI provider: {settings.ai_provider}")
            print("Phase 2 structured services available; use --mock-demo for offline fixtures.")
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
    except (ApplicationError, ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
