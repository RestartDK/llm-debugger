# MCP Server SSE Setup for Cursor

## Overview

The MCP server now supports Server-Sent Events (SSE) transport, allowing Cursor to connect remotely without local setup.

**Server URL:** `https://coolify.scottbot.party/llm_debugger`

## How It Works

1. **SSE Stream** (`GET /sse`): Opens a persistent connection for receiving responses
2. **Message Endpoint** (`POST /sse/message`): Sends MCP protocol requests

## Configuring Cursor

### Option 1: SSE Transport (Recommended)

1. Open Cursor Settings (Cmd+, or Ctrl+,)
2. Go to **Features** → **Model Context Protocol**
3. Click **Edit Config** or **+ Add New MCP Server**
4. Add configuration:

```json
{
  "mcpServers": {
    "debug-context": {
      "type": "sse",
      "url": "https://coolify.scottbot.party/llm_debugger/sse"
    }
  }
}
```

### Option 2: HTTP Transport (If Supported)

Some MCP clients support direct HTTP:

```json
{
  "mcpServers": {
    "debug-context": {
      "type": "http",
      "url": "https://coolify.scottbot.party/llm_debugger",
      "endpoints": {
        "message": "/sse/message",
        "sse": "/sse"
      }
    }
  }
}
```

## Testing the SSE Endpoint

### Test 1: Check SSE Connection

```bash
curl -N https://coolify.scottbot.party/llm_debugger/sse
```

You should see:
```
: connected

data: {"jsonrpc":"2.0","method":"connection","params":{"status":"connected","connection_id":"..."}}
```

### Test 2: Send Initialize Request

```bash
curl -X POST https://coolify.scottbot.party/llm_debugger/sse/message \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    }
  }'
```

Expected response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {"tools": {}},
    "serverInfo": {
      "name": "Debug Context MCP Server",
      "version": "0.1.0"
    }
  }
}
```

### Test 3: List Tools

```bash
curl -X POST https://coolify.scottbot.party/llm_debugger/sse/message \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }'
```

Expected response should include 4 tools:
- `submit_code_changes_mcp`
- `get_project_context_mcp`
- `get_code_chunk_context_mcp`
- `get_mcp_documentation_mcp`

### Test 4: Call a Tool

```bash
curl -X POST https://coolify.scottbot.party/llm_debugger/sse/message \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "get_mcp_documentation_mcp",
      "arguments": {}
    }
  }'
```

## Available MCP Tools

Once connected, these tools are available:

1. **submit_code_changes_mcp**
   - Submit code changes for debugging context
   - Parameters: `format_type`, `content`, `file_path`, `line_numbers`, `relationships`

2. **get_project_context_mcp**
   - Returns project metadata and high-level summary
   - No parameters

3. **get_code_chunk_context_mcp**
   - Returns debugging context for specific code chunks
   - Parameters: `file_path`, `line_numbers` (optional)

4. **get_mcp_documentation_mcp**
   - Returns documentation explaining available endpoints and tools
   - No parameters

## Troubleshooting

### SSE Endpoint Returns 405

If you see `405 Method Not Allowed`:
- Check that your reverse proxy (nginx/Cloudflare) allows GET requests to `/sse`
- Verify the endpoint is accessible: `curl -I https://coolify.scottbot.party/llm_debugger/sse`

### Connection Timeout

- Check firewall settings
- Verify the server is running
- Check reverse proxy timeout settings (SSE connections should have long timeouts)

### CORS Errors

The server includes CORS headers, but if you see CORS errors:
- Check browser console for specific errors
- Verify `Access-Control-Allow-Origin: *` header is present

### Tools Not Appearing

1. Check Cursor logs: Help → Toggle Developer Tools → Console
2. Verify the server responds to `tools/list` request
3. Check tool names match exactly (including `_mcp` suffix)

## Next Steps

1. ✅ SSE endpoint implemented
2. ✅ Tool names fixed to match FastMCP registration
3. ✅ CORS headers added
4. ⏳ Test with Cursor
5. ⏳ Verify tools appear in Cursor

## Notes

- The SSE endpoint uses a connection ID system for matching requests/responses
- Responses are returned directly from POST requests (standard HTTP)
- SSE stream can be used for server-initiated messages in the future
- All endpoints support CORS for browser-based clients

