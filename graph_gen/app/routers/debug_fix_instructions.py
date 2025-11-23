

def send_debugger_response(data: dict) -> dict:
    """Send debugger response. Placeholder implementation.
    containing test cases
    """

    prompt = """
    Apply the identified fixes for the errors/issues detected to the codebase.
    A separate debugging pipeline with code flow diagram has already identified necessary changes.
    
    Your job is to apply only the changes required to fix the issues, following these rules:

    1. Editing Rules

    Modify only files explicitly listed in the input.
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

    Format of the input:
    
    1. [Code Chunk N] - Include ACTUAL CODE (5-10 lines) that could be causing the bug
    2. File: <filepath> - Full file path where this code exists
    3. Lines: <start>-<end> - Line number range using dash format (e.g., "10-25")
    4. [Explanation] - What specific bug this code chunk might cause AND indicate which related code chunks are problematic vs. which look good (use descriptive text)
    5. [Relationships] - Structural/logical/data flow relationships to other code chunks (calls, dependencies, data flow) WITHOUT error context. MUST include the actual code from related chunks when referencing them (show the code, file path, and line range)
    
    Example input format (showing MULTIPLE chunks):
    
    [Code Chunk 1]
    File: src/utils.py
    Lines: 15-24
    
    def process_data(items):
        result = []
        for item in items:
            if item is None:
                continue
            result.append(item * 2)
        return result
    
    [Explanation]
    This function doesn't handle the case where items is None or empty, which could cause a TypeError when iterating. Code Chunk 2 (calculate_totals) is problematic because it calls this function without checking if data is None first. Code Chunk 3 (API handler) looks good as it validates input before calling calculate_totals.
    
    [Relationships]
    This function is called by calculate_totals() function (see Code Chunk 2). The result is used by the API handler in Code Chunk 3. Receives data from the request processing pipeline.
    
    Related code from Code Chunk 2:
    File: src/calculations.py
    Lines: 8-12
    def calculate_totals(data):
        processed = process_data(data)
        return sum(processed)
    
    [Code Chunk 2]
    File: src/calculations.py
    Lines: 8-12
    
    def calculate_totals(data):
        processed = process_data(data)
        return sum(processed)
    
    [Explanation]
    This function calls process_data() without validating that data is None first, which will cause a TypeError. Code Chunk 1 (process_data) is problematic because it doesn't handle None input. Code Chunk 3 (API handler) looks good as it validates input.
    
    [Relationships]
    Calls process_data() from Code Chunk 1. Called by API handler in Code Chunk 3. Part of the data processing pipeline.
    
    Related code from Code Chunk 1:
    File: src/utils.py
    Lines: 15-24
    def process_data(items):
        result = []
        for item in items:
            if item is None:
                continue
            result.append(item * 2)
        return result

    """

    return {"status": "placeholder"}
