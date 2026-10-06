"""Reusable UTF-8 template loading and single-pass ${variable} rendering."""
from collections.abc import Mapping
from pathlib import Path
from string import Template
from .errors import PromptError


class PromptLoader:
    def __init__(self, directory: Path | str):
        self.directory = Path(directory).resolve()

    def load(self, name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise PromptError("Template name must be a non-empty relative path")
        if Path(name).is_absolute():
            raise PromptError("Template name must be a relative path")
        path = (self.directory / name).resolve()
        if not path.is_relative_to(self.directory):
            raise PromptError("Template path must remain inside the prompt directory")
        try:
            template = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise PromptError(f"Prompt template not found: {name}") from exc
        except (OSError, UnicodeError) as exc:
            raise PromptError(f"Cannot read UTF-8 prompt template: {name}") from exc
        if not template.strip():
            raise PromptError(f"Prompt template is empty: {name}")
        return template


class PromptRenderer:
    def render(self, template: str, variables: Mapping[str, str]) -> str:
        if not isinstance(template, str) or not template.strip():
            raise PromptError("Prompt template must be non-empty text")
        parsed = Template(template)
        if not parsed.is_valid():
            raise PromptError("Invalid placeholder syntax; use ${name}, and $$ for a literal dollar")
        missing = set(parsed.get_identifiers()) - variables.keys()
        if missing:
            raise PromptError(f"Missing prompt variables: {', '.join(sorted(missing))}")
        for name in parsed.get_identifiers():
            if not isinstance(variables[name], str):
                raise PromptError(f"Prompt variable {name} must be a string")
        # Single substitution: inserted data containing ${...} is not re-rendered.
        return parsed.substitute(variables)
