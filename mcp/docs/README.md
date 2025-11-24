# MCP Server Documentation

This directory contains all documentation for the MCP Debug Context Server.

## Documentation Files

- **SSE_SETUP.md** - Guide for configuring Cursor to use SSE transport (remote HTTP setup)
- **ADDING_NEW_TOOLS.md** - Guide for adding new MCP tools to the server

## Quick Start

### For Remote SSE Connection (Recommended)
See [SSE_SETUP.md](./SSE_SETUP.md) for configuring Cursor with SSE transport.

## Testing

Test scripts are located in the `../tests/` directory:
- `test_http.sh` - Test HTTP endpoints
- `test_mcp.py` - Test MCP stdio connection

## Server URL

- **Production**: https://coolify.scottbot.party/llm_debugger
- **SSE Endpoint**: https://coolify.scottbot.party/llm_debugger/sse
- **Message Endpoint**: https://coolify.scottbot.party/llm_debugger/sse/message

