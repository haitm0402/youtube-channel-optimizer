"""Ports for future adapters. Core never imports a provider SDK."""
from typing import Protocol
from models import CompetitorInput


class TextGenerator(Protocol):
    def generate(self, *, prompt: str) -> str:
        """Generate text through a replaceable provider adapter."""
        ...


class CompetitorSource(Protocol):
    def fetch(self, url: str) -> CompetitorInput:
        """Obtain competitor data through a future source adapter."""
        ...
