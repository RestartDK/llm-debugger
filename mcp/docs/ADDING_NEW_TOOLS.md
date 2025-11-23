# Adding New MCP Tools

This guide explains how to add new tools to the Debug Context MCP Server.

## Overview

MCP tools are Python functions decorated with `@mcp.tool()` that are automatically discovered and exposed to MCP clients (like Cursor). FastMCP handles tool registration, schema generation, and execution automatically.

## Step-by-Step Process

### 1. Define Your Tool Function

Create a Python function in `main.py` (or import it from another module). The function can be:
- **Synchronous**: Regular Python function
- **Asynchronous**: `async def` function

**Example - Synchronous Tool:**
```python
@mcp.tool()
def my_new_tool(param1: str, param2: int = 10) -> str:
    """
    Description of what this tool does.
    
    This description will be shown to the LLM when it discovers available tools.
    Be detailed and clear about:
    - What the tool does
    - What parameters it expects
    - What it returns
    - Any important constraints or requirements
    
    Args:
        param1: Description of param1
        param2: Description of param2 (optional, defaults to 10)
        
    Returns:
        Description of return value
    """
    # Your tool logic here
    result = f"Processed {param1} with {param2}"
    return result
```

**Example - Asynchronous Tool:**
```python
@mcp.tool()
async def my_async_tool(query: str) -> str:
    """
    Async tool example.
    
    Use async tools for I/O-bound operations like API calls, database queries, etc.
    """
    import asyncio
    await asyncio.sleep(0.1)  # Simulate async operation
    return f"Query result: {query}"
```

### 2. Tool Registration

The `@mcp.tool()` decorator automatically:
- Registers the function with FastMCP
- Generates JSON schema from function signature and type hints
- Makes it discoverable via `tools/list` MCP protocol method
- Handles execution when `tools/call` is invoked

**No additional registration code needed!** FastMCP discovers all decorated functions automatically.

### 3. Tool Function Requirements

#### Function Signature
- Use type hints for all parameters (required for schema generation)
- Return type hint is recommended but optional
- Parameters can have default values (makes them optional in schema)

#### Docstring Best Practices
The docstring is critical - it's what the LLM sees when deciding whether to use your tool:

1. **First line**: Brief summary (used as short description)
2. **Body**: Detailed explanation including:
   - What the tool does
   - When to use it
   - Parameter descriptions
   - Return value description
   - Examples if helpful
   - Important constraints or requirements

**Good Example:**
```python
@mcp.tool()
def submit_code_context_mcp(text: str) -> str:
    """
    Submit potential bug areas from codebase analysis.
    
    REQUIRES MULTIPLE CODE CHUNKS in sequence, each with ACTUAL CODE BLOCKS (5-10 lines).
    
    WORKFLOW: When a user reports a bug/error, scan the codebase to identify potential 
    bug areas related to the reported issue. Send ALL candidate code chunks in ONE tool call.
    
    Format: Repeat this pattern for EACH potential bug area found:
    1. [Code Chunk N] - Include ACTUAL CODE (5-10 lines)
    2. File: <filepath> - Full file path
    3. Lines: <start>-<end> - Line number range
    4. [Explanation] - What bug this might cause
    5. [Relationships] - How it relates to other chunks
    
    Args:
        text: Raw text containing code chunks with format: [Code Chunk N], File, Lines, 
              [Explanation], [Relationships]. See tool description for full format requirements.
              
    Returns:
        Success message with filename where context was saved.
    """
    # Implementation...
```

### 4. Tool Discovery

FastMCP automatically discovers tools through:
1. `_tool_manager._tools` - Private attribute containing registered tools
2. `get_tools()` - Async method returning tool dictionary
3. `list_tools()` - Method returning MCP-formatted tool list

The `tools/list` handler in `core/mcp_routes.py` uses these methods to return tools to clients.

### 5. Testing Your Tool Locally

#### Test Tool Registration
```python
# In main.py or a test file
from main import mcp

# Check if tool is registered
tools = await mcp.get_tools()
assert "my_new_tool" in tools
```

#### Test Tool Execution
```python
# Direct function call (for unit testing)
result = my_new_tool("test", 5)
assert result == "Processed test with 5"

# Via FastMCP (for integration testing)
result = await mcp._call_tool_mcp("my_new_tool", {"param1": "test", "param2": 5})
```

#### Test via MCP Protocol
Start the server and use curl:
```bash
# List tools
curl -X POST http://localhost:8000/sse/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'

# Call tool
curl -X POST http://localhost:8000/sse/message \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "my_new_tool",
      "arguments": {"param1": "test", "param2": 5}
    }
  }'
```

### 6. Deployment Considerations

1. **Tool Discovery**: After deployment, tools are automatically discovered. No configuration changes needed.

2. **Tool Schema**: FastMCP generates schemas automatically from function signatures. Ensure type hints are accurate.

3. **Error Handling**: Wrap tool logic in try/except blocks and return meaningful error messages:
   ```python
   @mcp.tool()
   def my_tool(param: str) -> str:
       try:
           # Tool logic
           return result
       except Exception as e:
           logger.error(f"Tool error: {e}", exc_info=True)
           return f"Error: {str(e)}"
   ```

4. **Logging**: Use the logger for debugging:
   ```python
   import logging
   logger = logging.getLogger(__name__)
   
   @mcp.tool()
   def my_tool(param: str) -> str:
       logger.info(f"Tool called with param: {param}")
       # ...
   ```

5. **Synchronous vs Asynchronous**: 
   - Use **sync** functions for CPU-bound or simple operations
   - Use **async** functions for I/O-bound operations (API calls, file I/O, etc.)
   - FastMCP handles both correctly

## Complete Example: Adding a New Tool

Here's a complete example of adding a new tool from scratch:

### Step 1: Add Tool Function to `main.py`

```python
# In llm-debugger/mcp/main.py

@mcp.tool()
def get_project_summary() -> str:
    """
    Get a summary of the current project structure and key files.
    
    Returns a formatted string describing:
    - Project structure
    - Key files and their purposes
    - Main entry points
    
    Returns:
        Formatted project summary string
    """
    import os
    
    summary_parts = []
    summary_parts.append("Project Structure:\n")
    
    # Walk through project directory
    for root, dirs, files in os.walk("."):
        level = root.replace(".", "").count(os.sep)
        indent = " " * 2 * level
        summary_parts.append(f"{indent}{os.path.basename(root)}/\n")
        
        subindent = " " * 2 * (level + 1)
        for file in files[:5]:  # Limit to first 5 files per directory
            if not file.startswith(".") and not file.endswith(".pyc"):
                summary_parts.append(f"{subindent}{file}\n")
    
    return "".join(summary_parts)
```

### Step 2: Test Locally

```bash
# Start server
python main.py

# In another terminal, test tool discovery
curl -X POST http://localhost:8000/sse/message \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

### Step 3: Deploy

1. Commit your changes
2. Push to repository
3. Deploy to server
4. Tools are automatically available to MCP clients

## Troubleshooting

### Tool Not Appearing in `tools/list`

1. **Check registration**: Ensure `@mcp.tool()` decorator is present
2. **Check imports**: If tool is in another module, ensure it's imported in `main.py`
3. **Check logs**: Look for errors in tool discovery in `core/mcp_routes.py`
4. **Verify FastMCP instance**: Ensure you're using the same `mcp` instance that was initialized

### Tool Execution Fails

1. **Check function signature**: Ensure parameters match what's being passed
2. **Check error handling**: Look at server logs for exceptions
3. **Test function directly**: Call the function directly (not via MCP) to isolate issues
4. **Check return type**: Ensure function returns a string or JSON-serializable value

### Schema Generation Issues

1. **Type hints required**: FastMCP needs type hints to generate schemas
2. **Supported types**: Use `str`, `int`, `float`, `bool`, `list`, `dict`, or custom Pydantic models
3. **Optional parameters**: Use default values or `Optional[Type]` for optional params

## Best Practices

1. **Clear Descriptions**: Write detailed docstrings - they're what the LLM reads
2. **Type Hints**: Always use type hints for better schema generation
3. **Error Handling**: Wrap tool logic in try/except and return meaningful errors
4. **Logging**: Log tool calls for debugging: `logger.info(f"Tool {tool_name} called with {args}")`
5. **Idempotency**: Design tools to be idempotent when possible (safe to call multiple times)
6. **Validation**: Validate inputs early and return clear error messages
7. **Documentation**: Keep this guide updated when adding new patterns or requirements

## Related Files

- `main.py` - Tool definitions and FastMCP server setup
- `core/mcp_routes.py` - Tool discovery and execution handlers
- `core/mcp_tools.py` - Shared tool utility functions
- `docs/` - Additional documentation

## See Also

- FastMCP Documentation: https://gofastmcp.com
- MCP Protocol Spec: https://modelcontextprotocol.io
- Existing tools: `submit_code_context_mcp()`, `fetch_instructions_from_debugger()` in `main.py`

