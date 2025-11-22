# Update MCP Tool for Bug Analysis Workflow

## Overview

Modify the `submit_code_context_mcp` tool to guide Cursor's coding agent through a bug analysis workflow:

1. When user reports a bug/error, agent scans the codebase to identify potential bug areas
2. Agent sends ALL candidate code chunks in one tool call
3. Format: Code chunks with file names, line number ranges (dash format), explanations (what bug might occur + which related chunks are problematic vs. good), and structural relationships (logical/data flow only)

## Changes Required

### 1. Update Tool Description in `main.py`

**File**: `llm-debugger/mcp/main.py`

Update the `@mcp.tool()` decorator docstring for `submit_code_context_mcp` to:

- Instruct agent to scan codebase when user reports a bug/error
- Specify general scanning approach (look for code related to reported issue)
- Change format from BEFORE/AFTER to: Code Chunk + File Name + Line Range + Explanation + Relationships
- Explanation should indicate: what bug this might cause AND which related chunks are problematic vs. which look good
- Relationships should be structural/logical/data flow only (calls, dependencies, data flow) without error context
- Emphasize sending ALL potential bug areas in one tool call
- Include clear example showing new format

**Key changes**:

- Remove BEFORE/AFTER format
- Add requirement for file names and line number ranges (dash format: "10-25")
- Add instructions for codebase scanning workflow when bug is reported
- Update example to show new format with explanation indicating problematic vs. good related chunks
- Clarify relationships are structural only

### 2. Update Tool Schema in `mcp_routes.py`

**File**: `llm-debugger/mcp/core/mcp_routes.py`

Update `get_tools_list_schema()` function:

- Update the `description` field to match new workflow (scan on bug report, send all at once)
- Update the `inputSchema` description to reflect new format requirements
- Remove references to BEFORE/AFTER blocks
- Add requirements for file names, line ranges (dash format), and explanation format

### 3. Storage Format (No Changes Needed)

**File**: `llm-debugger/mcp/core/storage.py`

The storage function `save_code_context()` already accepts raw text, so no changes needed. The format will be handled by the tool description instructing the agent on what to send.

## Implementation Details

### New Tool Description Format

The tool should instruct the agent to:

1. **Before calling this tool**: When user reports a bug/error, scan the codebase to identify potential bug areas related to the reported issue.

2. **Format for each code chunk**:

   - `[Code Chunk N]` - Actual code (5-10 lines)
   - `File: <filepath>` - Full file path
   - `Lines: <start>-<end>` - Line number range using dash format (e.g., "10-25")
   - `[Explanation]` - What specific bug this code chunk might cause AND indicate which related code chunks are problematic vs. which look good (use descriptive text)
   - `[Relationships]` - Structural/logical/data flow relationships to other code chunks (calls, dependencies, data flow) WITHOUT error context

3. **Sequence**: Send ALL potential bug areas in one tool call, with multiple chunks in sequence (Code Chunk 1 → Explanation → Relationships → Code Chunk 2 → ...)

### Example Format

```
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
```

## Files to Modify

1. `llm-debugger/mcp/main.py` - Update `submit_code_context_mcp` tool docstring
2. `llm-debugger/mcp/core/mcp_routes.py` - Update `get_tools_list_schema()` description and inputSchema

## Testing Considerations

After deployment, verify:

- Tool description clearly instructs codebase scanning when bug is reported
- Format requirements are explicit (file names, line ranges with dash format, no BEFORE/AFTER)
- Explanation format includes bug description AND indicates problematic vs. good related chunks
- Relationships section focuses on structural/logical/data flow only
- Multiple chunks sequence is maintained
- Agent understands to send all chunks in one tool call

## Implementation Status

✅ **Completed** - Both files have been updated:

- `llm-debugger/mcp/main.py` - Tool description updated with bug analysis workflow
- `llm-debugger/mcp/core/mcp_routes.py` - Tool schema updated to match new format