# Testing MCP Server Connection to Cursor

This guide will help you test and debug the MCP server connection to Cursor.

## Prerequisites

1. Make sure you have Python 3.12+ installed
2. Install dependencies:
   ```bash
   cd llm-debugger/mcp
   pip install -e .
   ```

## Step 1: Test MCP Server Locally

Run the test script to verify the MCP server works:

```bash
cd llm-debugger/mcp
python test_mcp.py
```

This will:
- Test the MCP server initialization
- List available tools
- Test tool execution

**Expected Output:**
- Should show 4 tools: `submit_code_changes_mcp`, `get_project_context_mcp`, `get_code_chunk_context_mcp`, `get_mcp_documentation_mcp`
- Should successfully execute a tool

## Step 2: Test MCP Server Manually (stdio mode)

Test the server directly in stdio mode:

```bash
cd llm-debugger/mcp
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python main.py
```

You should see a JSON-RPC response.

## Step 3: Configure Cursor

1. Open Cursor Settings (Cmd+, on Mac, Ctrl+, on Windows/Linux)
2. Go to **Features** → **Model Context Protocol** (or search for "MCP" in settings)
3. Click **Edit Config** or add a new MCP server configuration
4. Add the following configuration:

```json
{
  "mcpServers": {
    "debug-context": {
      "command": "python",
      "args": [
        "/Users/scottwilliams/Desktop/AIEHackathon/llm-debugger/mcp/main.py"
      ],
      "env": {}
    }
  }
}
```

**Important:** Replace the path with the actual absolute path to your `main.py` file.

Alternatively, if you have a virtual environment:

```json
{
  "mcpServers": {
    "debug-context": {
      "command": "/path/to/venv/bin/python",
      "args": [
        "/Users/scottwilliams/Desktop/AIEHackathon/llm-debugger/mcp/main.py"
      ],
      "env": {}
    }
  }
}
```

## Step 4: Verify Connection in Cursor

1. Restart Cursor after adding the configuration
2. Open Command Palette (Cmd+Shift+P / Ctrl+Shift+P)
3. Type: `MCP: List Servers`
4. You should see `debug-context` listed and connected

## Step 5: Test MCP Tools in Cursor

Once connected, you can test the tools by asking Cursor to use them:

1. In the chat, try: "Use the get_mcp_documentation_mcp tool to show me the documentation"
2. Or: "Use get_project_context_mcp to get the project context"

## Troubleshooting

### Issue: MCP server not appearing in Cursor

**Check:**
1. Verify the path to `main.py` is correct and absolute
2. Check Cursor logs: Help → Toggle Developer Tools → Console tab
3. Make sure Python is in your PATH or use full path to Python executable

### Issue: "Command not found" error

**Solution:**
- Use full absolute path to Python executable
- Or ensure Python is in your system PATH

### Issue: Import errors

**Solution:**
```bash
cd llm-debugger/mcp
pip install -e .
```

### Issue: Server starts but tools don't work

**Check:**
1. Run `python test_mcp.py` to verify server works standalone
2. Check Cursor logs for error messages
3. Verify all dependencies are installed

### Debug Mode

To see what Cursor is sending to the MCP server, you can modify `main.py` temporarily to log stdin:

```python
import sys
import json

# Add at the top of main.py (before mcp.run())
if not sys.stdin.isatty():
    import logging
    logging.basicConfig(level=logging.DEBUG, filename='mcp_debug.log')
    logger = logging.getLogger(__name__)
```

## Manual Testing Commands

### Test 1: Initialize
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python main.py
```

### Test 2: List Tools
```bash
(echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'; echo '{"jsonrpc":"2.0","id":2,"method":"tools/list"}') | python main.py
```

### Test 3: Call Tool
```bash
(echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'; echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_mcp_documentation_mcp","arguments":{}}}') | python main.py
```

## Next Steps

Once the MCP server is connected:
1. Test each tool individually
2. Verify data is being stored correctly
3. Check that the REST API endpoints also work (run `python main.py` in a terminal to start HTTP server)

