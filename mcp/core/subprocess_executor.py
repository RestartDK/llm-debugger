"""
Subprocess execution system for running LLM-generated Python code chunks.
"""
from __future__ import annotations

import inspect
import subprocess
import sys
import time
import traceback
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from .agent import LlmDebugAgent


class SubprocessExecutionResult(BaseModel):
    """
    Result of executing a subprocess command.
    """
    success: bool
    stdout: str
    stderr: str
    returncode: int
    execution_time: float
    error_message: Optional[str] = None


class GeneratedCommand(BaseModel):
    """
    LLM-generated Python command string.
    """
    command: str = Field(..., description="Complete Python script string to execute via python -c")
    reasoning: Optional[str] = Field(default=None, description="Explanation of what this command does")


def build_command_generation_prompt(
    code_chunks: List[str],
    test_code: str,
    task_description: Optional[str] = None,
) -> str:
    """
    Build prompt for LLM to generate a complete Python script command.
    """
    chunks_text = "\n\n".join([f"# Code Chunk {i+1}:\n{chunk}" for i, chunk in enumerate(code_chunks)])
    
    prompt = f"""
You are a Python code generator. Your task is to create a complete, standalone Python script that combines code chunks and test code.

CRITICAL REQUIREMENTS:
1. NO external dependencies - use only Python standard library
2. The script must be completely self-contained and executable via `python -c "..."` 
3. Mock or stub any external dependencies (APIs, databases, frameworks) inline
4. Combine all code chunks into a single executable script
5. Include the test code at the end to verify the code works
6. Add any necessary imports, stubs, or mocks within the script itself
7. The script should be a single string that can be passed to `python -c`

Code Chunks to Combine:
{chunks_text}

Test Code to Execute:
```python
{test_code}
```

Task Description:
{task_description or "Execute the code chunks and run the test"}

Generate a complete Python script string that:
- Combines all code chunks
- Adds necessary mocks/stubs for any external dependencies
- Includes the test code
- Can be executed via `python -c "your_script_here"`

Return ONLY the Python code string, no explanations or markdown formatting.
"""
    return prompt


def build_command_repair_prompt(
    failed_command: str,
    stdout: str,
    stderr: str,
    returncode: int,
    attempt_number: int,
) -> str:
    """
    Build prompt for LLM to repair a failed command.
    """
    prompt = f"""
You are fixing a Python script that failed to execute. This is attempt #{attempt_number}.

Failed Command:
```python
{failed_command}
```

Execution Output:
- Return Code: {returncode}
- Stdout:
{stdout[:1000] if stdout else "(empty)"}

- Stderr:
{stderr[:1000] if stderr else "(empty)"}

Your task: Generate a FIXED version of the Python script that:
1. Fixes the error(s) shown in stderr
2. Maintains the same functionality
3. Still uses NO external dependencies (only standard library)
4. Is completely self-contained and executable via `python -c "..."`

Return ONLY the fixed Python code string, no explanations or markdown formatting.
"""
    return prompt


def generate_subprocess_command(
    agent: LlmDebugAgent,
    code_chunks: List[str],
    test_code: str,
    task_description: Optional[str] = None,
) -> GeneratedCommand:
    """
    Use LLM to generate a complete Python script command from code chunks and test code.
    """
    prompt = build_command_generation_prompt(code_chunks, test_code, task_description)
    
    # Log the call
    frame = inspect.currentframe()
    if frame:
        caller_frame = frame.f_back
        if caller_frame:
            filename = caller_frame.f_code.co_filename
            lineno = caller_frame.f_lineno
            func_name = caller_frame.f_code.co_name
            print(
                f"[groq_call] File: {filename}, Line: {lineno}, Function: {func_name}, "
                f"Output Type: unstructured (text only), Action: generate_subprocess_command",
                file=sys.stderr,
            )
    
    try:
        run_result = agent.agent.run_sync(prompt)
        command_text = run_result.output.strip()
        
        # Remove markdown code blocks if present
        if command_text.startswith("```python"):
            command_text = command_text[9:]
        if command_text.startswith("```"):
            command_text = command_text[3:]
        if command_text.endswith("```"):
            command_text = command_text[:-3]
        command_text = command_text.strip()
        
        print(f"[subprocess_executor] Generated command length: {len(command_text)} chars", file=sys.stderr)
        print(f"[subprocess_executor] Command preview: {command_text[:200]}...", file=sys.stderr)
        
        return GeneratedCommand(command=command_text)
    except Exception as e:
        print(f"[subprocess_executor] ERROR generating command: {e}", file=sys.stderr)
        print(f"[subprocess_executor] Traceback:\n{traceback.format_exc()}", file=sys.stderr)
        raise


def repair_subprocess_command(
    agent: LlmDebugAgent,
    failed_command: str,
    stdout: str,
    stderr: str,
    returncode: int,
    attempt_number: int,
) -> GeneratedCommand:
    """
    Use LLM to repair a failed subprocess command based on error output.
    """
    prompt = build_command_repair_prompt(failed_command, stdout, stderr, returncode, attempt_number)
    
    # Log the call
    frame = inspect.currentframe()
    if frame:
        caller_frame = frame.f_back
        if caller_frame:
            filename = caller_frame.f_code.co_filename
            lineno = caller_frame.f_lineno
            func_name = caller_frame.f_code.co_name
            print(
                f"[groq_call] File: {filename}, Line: {lineno}, Function: {func_name}, "
                f"Output Type: unstructured (text only), Action: repair_subprocess_command, Attempt: {attempt_number}",
                file=sys.stderr,
            )
    
    try:
        run_result = agent.agent.run_sync(prompt)
        repaired_command = run_result.output.strip()
        
        # Remove markdown code blocks if present
        if repaired_command.startswith("```python"):
            repaired_command = repaired_command[9:]
        if repaired_command.startswith("```"):
            repaired_command = repaired_command[3:]
        if repaired_command.endswith("```"):
            repaired_command = repaired_command[:-3]
        repaired_command = repaired_command.strip()
        
        print(f"[subprocess_executor] Repaired command length: {len(repaired_command)} chars", file=sys.stderr)
        print(f"[subprocess_executor] Repaired command preview: {repaired_command[:200]}...", file=sys.stderr)
        
        return GeneratedCommand(command=repaired_command)
    except Exception as e:
        print(f"[subprocess_executor] ERROR repairing command: {e}", file=sys.stderr)
        print(f"[subprocess_executor] Traceback:\n{traceback.format_exc()}", file=sys.stderr)
        raise


def execute_subprocess_command(
    command: str,
    timeout: float = 10.0,
) -> SubprocessExecutionResult:
    """
    Execute a Python command via subprocess and capture output.
    
    Args:
        command: Python script string to execute via `python -c`
        timeout: Maximum execution time in seconds
        
    Returns:
        SubprocessExecutionResult with stdout, stderr, returncode, etc.
    """
    print(f"[subprocess_executor] Executing command (timeout={timeout}s)...", file=sys.stderr)
    print(f"[subprocess_executor] Command preview: {command[:200]}...", file=sys.stderr)
    
    start_time = time.time()
    
    try:
        process = subprocess.run(
            [sys.executable, "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # Don't raise on non-zero exit
        )
        
        execution_time = time.time() - start_time
        
        stdout = process.stdout or ""
        stderr = process.stderr or ""
        returncode = process.returncode
        
        success = returncode == 0
        
        error_message = None
        if not success:
            # Extract error message from stderr
            if stderr:
                # Try to get the last meaningful error line
                error_lines = [line.strip() for line in stderr.split("\n") if line.strip()]
                if error_lines:
                    error_message = error_lines[-1]
            if not error_message and stdout:
                error_message = "Command failed but no error message in stderr"
        
        print(
            f"[subprocess_executor] Execution completed: success={success}, "
            f"returncode={returncode}, time={execution_time:.3f}s",
            file=sys.stderr,
        )
        print(f"[subprocess_executor] Stdout length: {len(stdout)} chars", file=sys.stderr)
        print(f"[subprocess_executor] Stderr length: {len(stderr)} chars", file=sys.stderr)
        
        return SubprocessExecutionResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            execution_time=execution_time,
            error_message=error_message,
        )
        
    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time
        print(f"[subprocess_executor] Command timed out after {execution_time:.3f}s", file=sys.stderr)
        return SubprocessExecutionResult(
            success=False,
            stdout="",
            stderr=f"Command execution timed out after {timeout} seconds",
            returncode=-1,
            execution_time=execution_time,
            error_message=f"Timeout after {timeout}s",
        )
    except Exception as e:
        execution_time = time.time() - start_time
        print(f"[subprocess_executor] ERROR executing command: {e}", file=sys.stderr)
        print(f"[subprocess_executor] Traceback:\n{traceback.format_exc()}", file=sys.stderr)
        return SubprocessExecutionResult(
            success=False,
            stdout="",
            stderr=str(e),
            returncode=-1,
            execution_time=execution_time,
            error_message=str(e),
        )

