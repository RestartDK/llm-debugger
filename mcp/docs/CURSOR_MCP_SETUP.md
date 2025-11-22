# Setting Up MCP Server for Cursor

## Summary

✅ **HTTP Server**: Working correctly at https://coolify.scottbot.party/llm_debugger
- All REST API endpoints are functional
- 7/8 endpoints tested successfully

⚠️ **MCP Stdio Server**: Needs testing/configuration for Cursor

## HTTP Endpoints Test Results

All endpoints tested successfully:
- ✅ `/health` - Health check
- ✅ `/` - Root endpoint  
- ✅ `/api/documentation` - Documentation
- ✅ `/api/project/context` - Project context
- ✅ `/api/changes/submit` - Submit changes (both formats)
- ✅ `/api/debug/chunk-context` - Get chunk context
- ⚠️ `/sse` - SSE endpoint (405 error - may be expected behind reverse proxy)

## Configuring Cursor MCP Connection

Cursor connects to MCP servers via **stdio** (standard input/output), not HTTP. You need to configure Cursor to run the Python script locally or via SSH.

### Option 1: Local MCP Server (Recommended for Testing)

If you want to run the MCP server locally on your machine:

1. **Install dependencies locally:**
   ```bash
   cd llm-debugger/mcp
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e .
   ```

2. **Configure Cursor:**
   - Open Cursor Settings (Cmd+, or Ctrl+,)
   - Go to **Features** → **Model Context Protocol**
   - Click **Edit Config** or add configuration
   - Add:

   ```json
   {
     "mcpServers": {
       "debug-context": {
         "command": "/Users/scottwilliams/Desktop/AIEHackathon/llm-debugger/mcp/venv/bin/python",
         "args": [
           "/Users/scottwilliams/Desktop/AIEHackathon/llm-debugger/mcp/main.py"
         ],
         "env": {}
       }
     }
   }
   ```

   **Important:** Use absolute paths and the Python executable from your virtual environment.

### Option 2: Remote MCP Server via SSH

If you want Cursor to connect to the VPS via SSH:

```json
{
  "mcpServers": {
    "debug-context": {
      "command": "ssh",
      "args": [
        "user@your-vps-ip",
        "cd /path/to/llm-debugger/mcp && /opt/venv/bin/python main.py"
      ],
      "env": {}
    }
  }
}
```

**Note:** This requires SSH key authentication set up.

### Option 3: Use HTTP/SSE Endpoint (If Supported)

Some MCP clients support HTTP transport. Check if Cursor supports this, or use the HTTP endpoints directly from your application.

## Testing the MCP Connection

After configuring Cursor:

1. **Restart Cursor** completely

2. **Check MCP Status:**
   - Open Command Palette (Cmd+Shift+P / Ctrl+Shift+P)
   - Type: `MCP: List Servers`
   - You should see `debug-context` listed

3. **Test Tools:**
   - In Cursor chat, try: "Use the get_mcp_documentation_mcp tool"
   - Or: "Call get_project_context_mcp to get project context"

## Troubleshooting

### MCP Server Not Appearing

1. **Check Cursor Logs:**
   - Help → Toggle Developer Tools → Console tab
   - Look for MCP-related errors

2. **Verify Python Path:**
   - Make sure the Python executable path is correct
   - Test running the script manually:
     ```bash
     echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python3 /path/to/main.py
     ```

3. **Check Dependencies:**
   - Ensure all packages are installed: `pip install -e .`
   - Verify FastMCP is installed: `pip list | grep fastmcp`

### Import Errors

If you see import errors:
```bash
cd llm-debugger/mcp
pip install -e .
```

### FastMCP Run Method

The current code uses `mcp.run()` for stdio mode. If this doesn't work, FastMCP might use a different method. Check the FastMCP documentation or try:

```python
# Alternative approaches:
# mcp.run(transport="stdio")
# or
if __name__ == "__main__":
    import sys
    if not sys.stdin.isatty():
        from fastmcp import serve_stdio
        serve_stdio(mcp)
```

## Available MCP Tools

Once connected, these tools will be available:

1. **submit_code_changes_mcp**
   - Submit code changes for debugging context
   - Parameters: format_type, content, file_path, line_numbers, relationships

2. **get_project_context_mcp**
   - Returns project metadata and high-level summary
   - No parameters

3. **get_code_chunk_context_mcp**
   - Returns debugging context for specific code chunks
   - Parameters: file_path, line_numbers (optional)

4. **get_mcp_documentation_mcp**
   - Returns documentation explaining available endpoints and tools
   - No parameters

## Next Steps

1. ✅ HTTP server is working - confirmed
2. ⏳ Test MCP stdio connection locally
3. ⏳ Configure Cursor with correct paths
4. ⏳ Verify tools are accessible in Cursor

## Testing Commands

### Test HTTP Endpoints:
```bash
curl https://coolify.scottbot.party/llm_debugger/health
curl https://coolify.scottbot.party/llm_debugger/api/documentation
```

### Test MCP Stdio Locally:
```bash
cd llm-debugger/mcp
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python3 main.py
```

