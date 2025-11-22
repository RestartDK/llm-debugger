# MCP Server Documentation

This directory contains all documentation for the MCP Debug Context Server.

## Documentation Files

- **CURSOR_MCP_SETUP.md** - Guide for setting up MCP server connection with Cursor (local stdio setup)
- **SSE_SETUP.md** - Guide for configuring Cursor to use SSE transport (remote HTTP setup)
- **DEPLOYMENT_STATUS.md** - Current deployment status and testing results
- **TEST_HTTP.md** - HTTP endpoint testing guide
- **TEST_MCP.md** - MCP stdio testing guide

## Quick Start

### For Remote SSE Connection (Recommended)
See [SSE_SETUP.md](./SSE_SETUP.md) for configuring Cursor with SSE transport.

### For Local Stdio Connection
See [CURSOR_MCP_SETUP.md](./CURSOR_MCP_SETUP.md) for local setup instructions.

## Testing

Test scripts are located in the `../tests/` directory:
- `test_http.sh` - Test HTTP endpoints
- `test_mcp.py` - Test MCP stdio connection

## Server URL

- **Production**: https://coolify.scottbot.party/llm_debugger
- **SSE Endpoint**: https://coolify.scottbot.party/llm_debugger/sse
- **Message Endpoint**: https://coolify.scottbot.party/llm_debugger/sse/message

