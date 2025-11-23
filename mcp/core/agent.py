from __future__ import annotations


import os
from typing import Dict, List, Optional, Sequence

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.models.groq import GroqModel

from .debug_analysis_llm import (
    BlockInfo,
    DebugAnalysis,
    FailedTest,
    RuntimeStateSnapshot,
    analyze_failed_test,
)
from .source_enhancement_llm import (
    EnhancedSource,
    enhance_source_code,
)
from .test_generation_llm import GeneratedTestSuite, generate_tests_for_code


class LlmDebugAgent:
    """
    Thin facade around a configured pydantic-ai Agent.
    """

    def __init__(
        self,
        *,
        model_name: str = "openai/gpt-oss-120b",
        agent: PydanticAgent | None = None,
    ):
        """
        Args:
            model_name: Model to target (defaults to Groq-hosted model).
            agent: Optional fully constructed pydantic-ai Agent (primarily for tests).
        """

        if agent:
            self._agent = agent
            return

        model = GroqModel(model_name)
        self._agent = PydanticAgent(model, retries=4)

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

    def enhance_sources_for_execution(
        self,
        *,
        sources: Sequence[Dict[str, str]],
        error_context: Optional[List[Dict[str, str]]] = None,
    ) -> List[EnhancedSource]:
        """
        Enhance source code snippets to be self-contained and executable.
        
        Args:
            sources: List of source dicts with "file_path" and "code" keys
            error_context: Optional list of error dicts from previous execution attempts
            
        Returns:
            List of EnhancedSource objects with enhanced code
        """
        return enhance_source_code(
            agent=self._agent,
            sources=sources,
            error_context=error_context,
        )
