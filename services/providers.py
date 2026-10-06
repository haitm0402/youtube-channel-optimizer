"""Composition helpers outside core; real SDK adapters can be added here later."""
from config import Settings
from core.contracts import TextGenerator
from core.errors import ProviderError
from .mock import MockTextGenerator


def create_text_generator(settings: Settings) -> TextGenerator:
    if settings.ai_provider == "mock":
        return MockTextGenerator()
    raise ProviderError(f"Provider '{settings.ai_provider}' has no implemented adapter; use 'mock'")
