"""Phase 1 diagnostic entry point. No GUI, generation, or network access."""
import argparse
from config import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the project configuration")
    parser.add_argument("--config", help="Path to an optional TOML configuration")
    args = parser.parse_args()
    settings = load_settings(args.config)
    if not settings.prompts_dir.is_dir():
        parser.error(f"Prompt directory does not exist: {settings.prompts_dir}")
    print(f"Configuration valid. AI provider: {settings.ai_provider}")
    print("Phase 1 scaffold; generation is not implemented.")


if __name__ == "__main__":
    main()
