"""Deterministic offline provider using complete, version-controlled JSON fixtures."""
import json
from pathlib import Path
from core.errors import ProviderError


class MockTextGenerator:
    """Select a fixture by the template's exact first line, never by user data.

    This simulates response shapes, not LLM quality, scraping, or visual analysis.
    """
    def generate(self, *, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ProviderError("Mock provider requires a non-empty prompt")
        task = prompt.splitlines()[0]
        filenames = {
            "# Task: analyze_competitor": "analysis.json",
            "# Task: generate_names": "names.json",
            "# Task: generate_package": "package.json",
        }
        if task not in filenames:
            raise ProviderError("Mock provider does not recognize this prompt task")
        try:
            response = json.loads((Path(__file__).resolve().parent / "mock_data" / filenames[task]).read_text(encoding="utf-8"))
            if task == "# Task: generate_package":
                # Keep selected branding in the mock output without interpreting instructions.
                selection_line = next(line for line in prompt.splitlines() if line.startswith("Selected name JSON: "))
                selected_name = json.loads(selection_line.removeprefix("Selected name JSON: "))
                if not isinstance(selected_name, str) or not selected_name.strip():
                    raise ValueError("Invalid selection")
                response["channel_description"] = f"{selected_name} — không gian nhạc Việt thư giãn mỗi tối. Khám phá acoustic và ballad qua các playlist theo tâm trạng."
        except (OSError, UnicodeError, ValueError, StopIteration) as exc:
            raise ProviderError("Mock response fixture or prompt context is invalid") from exc
        return json.dumps(response, ensure_ascii=False, allow_nan=False)
