"""Application orchestration; depends only on the TextGenerator port."""
from dataclasses import asdict
import json
from .contracts import TextGenerator
from .errors import ApplicationError, ProviderError
from .prompts import PromptLoader, PromptRenderer
from .responses import parse_response
from models import ChannelNameResult, ChannelPackage, CompetitorAnalysis, CompetitorInput


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class _StructuredService:
    def __init__(self, generator: TextGenerator, loader: PromptLoader,
                 renderer: PromptRenderer | None = None):
        self.generator = generator
        self.loader = loader
        self.renderer = renderer if renderer is not None else PromptRenderer()

    def _generate(self, template, variables, factory):
        prompt = self.renderer.render(self.loader.load(template), variables)
        try:
            response = self.generator.generate(prompt=prompt)
        except ApplicationError:
            raise
        except Exception as exc:
            # Do not copy SDK error details (possibly credentials) into application messages.
            raise ProviderError("Text provider failed to generate a response") from exc
        return parse_response(response, factory)


class CompetitorAnalysisService(_StructuredService):
    def analyze(self, competitor: CompetitorInput) -> CompetitorAnalysis:
        if not isinstance(competitor, CompetitorInput):
            raise ValueError("competitor must be a CompetitorInput")
        return self._generate("analyze_competitor.md", {"competitor_json": _json(asdict(competitor))},
                              CompetitorAnalysis.from_ai_dict)


class ChannelNameService(_StructuredService):
    def generate(self, analysis: CompetitorAnalysis) -> ChannelNameResult:
        if not isinstance(analysis, CompetitorAnalysis):
            raise ValueError("analysis must be a CompetitorAnalysis")
        # Legacy analysis may be loaded, but cannot bypass complete AI boundary validation.
        validated = CompetitorAnalysis.from_ai_dict(analysis.to_ai_dict())
        return self._generate("generate_names.md", {"analysis_json": _json(validated.to_ai_dict())},
                              ChannelNameResult.from_ai_dict)


class ChannelPackageService(_StructuredService):
    def generate(self, analysis: CompetitorAnalysis, names: ChannelNameResult,
                 selected_name: str) -> ChannelPackage:
        if not isinstance(analysis, CompetitorAnalysis) or not isinstance(names, ChannelNameResult):
            raise ValueError("analysis and names must be typed analysis/name results")
        validated = CompetitorAnalysis.from_ai_dict(analysis.to_ai_dict())
        # Revalidate collections in frozen models because their nested lists remain mutable.
        ChannelNameResult(names.names, names.best_recommendation)
        if selected_name not in [item.name for item in names.names]:
            raise ValueError("selected_name must exactly match a suggested name")
        return self._generate("generate_package.md", {
            "analysis_json": _json(validated.to_ai_dict()), "selected_name_json": _json(selected_name),
        }, ChannelPackage.from_ai_dict)
