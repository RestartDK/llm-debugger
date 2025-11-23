from __future__ import annotations


from typing import Optional, Sequence

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from .debug_analysis_llm import (
    BlockInfo,
    DebugAnalysis,
    FailedTest,
    RuntimeStateSnapshot,
    analyze_failed_test,
)
from .test_generation_llm import GeneratedTestSuite, generate_tests_for_code


class LlmDebugAgent:
    """
    Thin facade around a configured pydantic-ai Agent.
    """

    def __init__(
        self,
        *,
        model_name: str = "gemini-2.5-pro",
        vertex: bool = False,
        google_provider: GoogleProvider | None = None,
        agent: PydanticAgent | None = None,
    ):
        """
        Args:
            model_name: Gemini model to target.
            vertex: If True, configure GoogleProvider for Vertex AI instead of GLA.
            google_provider: Optional pre-configured provider (overrides model_name/vertex).
            agent: Optional fully constructed pydantic-ai Agent (primarily for tests).
        """

        if agent:
            self._agent = agent
            return

        provider = google_provider or GoogleProvider(vertexai=vertex)
        model = GoogleModel(model_name, provider=provider)
        self._agent = PydanticAgent(model)

    @property
    def agent(self) -> PydanticAgent:
        """
        Access to the underlying pydantic-ai Agent (e.g., for advanced usage).
        """

        return self._agent

    # ------------------------------------------------------------------ #
    # Domain helpers
    # ------------------------------------------------------------------ #

    def generate_tests_for_code(
        self, *, code_snippet: str, context: Optional[str] = None
    ) -> GeneratedTestSuite:
        """
        Produce a structured test suite suggestion for the provided code.
        """

        return generate_tests_for_code(
            agent=self._agent,
            code_snippet=code_snippet,
            context=context,
        )

    def analyze_failed_test(
        self,
        *,
        task_description: str,
        blocks: Sequence[BlockInfo],
        runtime_states: Sequence[RuntimeStateSnapshot],
        failed_test: FailedTest,
    ) -> DebugAnalysis:
        """
        Ask Gemini to inspect runtime state transitions and flag broken blocks.
        """

        return analyze_failed_test(
            agent=self._agent,
            task_description=task_description,
            blocks=blocks,
            runtime_states=runtime_states,
            failed_test=failed_test,
        )
