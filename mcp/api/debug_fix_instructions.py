"""
Debug fix instructions handling.
"""

from core.agent import LlmDebugAgent
from core.dummy_cfg import get_dummy_fix_instructions
from core.llm_workflow_orchestrator import apply_suggested_fixes_to_source

def get_task_description():

    return '''

Apply suggested fixes to the codebase.
A separate debugging pipeline has already identified:

Which test cases failed
The root cause analysis
Exact file names and line numbers involved
Proposed minimal fixes
Relevant diffs, stack traces, and context
Your job is to apply only the changes required to fix the issues, following these rules:

1. Editing Rules

Modify only files explicitly listed in the input.
For each file, apply the changes inside the input.
If a patch is ambiguous, ask for clarification instead of guessing.
Do not rewrite entire files unless the patch requires it.
Preserve formatting, imports, comments, and style of the existing codebase.
Never introduce new dependencies unless the patch explicitly instructs it.

2. Consistency Rules

Ensure all changes type-check and satisfy the project's conventions.
Ensure each fix is coherent with the runtime trace and failing test behavior.
If a patch interacts with a function called across multiple files, verify cross-file compatibility.
If removing or refactoring code, ensure references and calls remain valid.

3. Safety Rules

Do not create new files unless explicitly instructed.
Do not delete or rename files unless explicitly instructed.
Avoid speculative changes; stay strictly within the proposed patches.
If you need more context from a file, request it before editing.

'''

def send_debugger_response(data: dict) -> dict:
    """
    Accept debugger feedback payloads (e.g., user-selected fixes) and echo them.
    """

    
    task_description = data.get(
        "task_description", get_task_description()
    )

    instructions = data.get("instructions") or get_dummy_fix_instructions()
    agent = LlmDebugAgent()

    
    apply_suggested_fixes_to_source(
        agent=agent,
        task_description=task_description,
        instructions=instructions,
    )

    return {
        "status": "ok",
        "echo": data,
    }

