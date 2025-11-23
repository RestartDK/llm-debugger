"""
Debug fix instructions handling.
"""

from datetime import datetime
import os
import re
import logging
from typing import Callable, Optional

from core.agent import LlmDebugAgent
from core.dummy_cfg import get_dummy_fix_instructions
from core.llm_workflow_orchestrator import apply_suggested_fixes_to_source

logger = logging.getLogger(__name__)

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

def send_debugger_response(data: dict,
                           progress_callback: Optional[Callable[[str, str, float], None]] = None,
                           output_dir: str = "instructions"
                           ) -> dict:
    """
    Accept debugger feedback payloads (e.g., user-selected fixes) and echo them.
    """

    # Starting
    if progress_callback:
        progress_callback("starting", "Starting instructions saving...", 0.0)
    
    os.makedirs(output_dir, exist_ok=True)
    
    task_description = data.get(
        "task_description", get_task_description()
    )

    instructions = data.get("instructions") or get_dummy_fix_instructions()

    
    # Generate filename: YYYY-MM-DD_HH-MM.json
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"{timestamp}.txt"
    filepath = os.path.join(output_dir, filename)

    # Saving
    if progress_callback:
        progress_callback("saving", f"Saving instructions to {filename}...", 0.95)
    
    # Save to txt file
    with open(filepath, 'w') as f:
        f.write(task_description + '\n' + instructions)

    # Complete
    if progress_callback:
        progress_callback("complete", "Instructions saving complete.", 1.0)

        
    # agent = LlmDebugAgent()

    
    # apply_suggested_fixes_to_source(
    #     agent=agent,
    #     task_description=task_description,
    #     instructions=instructions,
    # )



    return {
        "status": "ok",
        "echo": data,
    }


def get_most_recent_instructions(instructions_dir: str = "instructions") -> str:
    """
    Read the most recent instruction file from the instructions directory.
    
    Only considers files matching the timestamp pattern YYYY-MM-DD_HH-MM.txt.
    Returns the raw file contents as a string.
    
    Args:
        instructions_dir: Directory containing instruction files (default: "instructions")
        
    Returns:
        String containing the file contents, or error message if file cannot be read
        
    Raises:
        Does not raise exceptions - returns error messages as strings instead
    """
    logger.info(f"Fetching most recent instructions from {instructions_dir}/ folder")
    
    try:
        # Check if directory exists
        if not os.path.exists(instructions_dir):
            error_msg = f"Error: Instructions directory '{instructions_dir}' does not exist"
            logger.error(error_msg)
            return error_msg
        
        # List all files in the directory
        all_files = os.listdir(instructions_dir)
        logger.info(f"Found {len(all_files)} files in {instructions_dir}/")
        
        # Filter files matching timestamp pattern YYYY-MM-DD_HH-MM.txt
        # Pattern: exactly 4 digits, dash, 2 digits, dash, 2 digits, underscore, 2 digits, dash, 2 digits, .txt
        timestamp_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.txt$')
        timestamped_files = [f for f in all_files if timestamp_pattern.match(f)]
        
        if not timestamped_files:
            error_msg = f"Error: No instruction files found in {instructions_dir}/ folder. Expected files matching pattern YYYY-MM-DD_HH-MM.txt"
            logger.warning(error_msg)
            return error_msg
        
        logger.info(f"Found {len(timestamped_files)} timestamped instruction files")
        
        # Parse timestamps and sort by most recent first
        def parse_timestamp(filename: str) -> datetime:
            """Extract timestamp from filename (YYYY-MM-DD_HH-MM.txt)"""
            try:
                timestamp_str = filename.replace('.txt', '')
                return datetime.strptime(timestamp_str, '%Y-%m-%d_%H-%M')
            except ValueError as e:
                logger.warning(f"Failed to parse timestamp from filename '{filename}': {e}")
                return datetime.min  # Put unparseable files at the end
        
        # Sort by timestamp (most recent first)
        sorted_files = sorted(timestamped_files, key=parse_timestamp, reverse=True)
        most_recent_file = sorted_files[0]
        most_recent_timestamp = parse_timestamp(most_recent_file)
        
        logger.info(f"Most recent instruction file: {most_recent_file} (timestamp: {most_recent_timestamp})")
        
        # Read the most recent file
        filepath = os.path.join(instructions_dir, most_recent_file)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                instructions = f.read()
            
            # Verify we read the complete file
            code_chunk_pos = instructions.find('[Code Chunk]')
            if code_chunk_pos > 0:
                logger.info(f"Retrieved instructions from {most_recent_file} (length: {len(instructions)} chars, task description: {code_chunk_pos} chars before [Code Chunk])")
            else:
                logger.warning(f"Warning: [Code Chunk] marker not found in {most_recent_file}")
                logger.info(f"Retrieved instructions from {most_recent_file} (length: {len(instructions)} chars)")
            
            return instructions
            
        except IOError as e:
            error_msg = f"Error: Failed to read instruction file '{most_recent_file}'. {str(e)}"
            logger.error(error_msg, exc_info=True)
            return error_msg
            
    except Exception as e:
        error_msg = f"Error fetching instructions: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg

