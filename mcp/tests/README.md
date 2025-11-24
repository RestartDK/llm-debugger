# MCP Server Test Scripts

This directory contains test scripts for the MCP Debug Context Server.

## Test Scripts

### test_http.sh
Automated HTTP endpoint testing script.

**Usage:**
```bash
cd tests
./test_http.sh https://YOUR_SERVER_URL/llm_debugger
```

**Tests:**
- Health check
- Root endpoint
- Documentation endpoint
- Project context
- Submit changes (structured and diff formats)
- Get chunk context
- SSE endpoint

### test_mcp.py
MCP stdio connection testing script.

**Usage:**
```bash
cd tests
python3 test_mcp.py
```

**Requirements:**
- Python 3.12+
- Dependencies installed: `pip install -e ..`

**Tests:**
- MCP server initialization
- Tools list
- Tool execution

## Running Tests

### HTTP Tests
```bash
cd /path/to/llm-debugger/mcp/tests
./test_http.sh https://YOUR_SERVER_URL/llm_debugger
```

### MCP Stdio Tests
```bash
cd /path/to/llm-debugger/mcp
pip install -e .
cd tests
python3 test_mcp.py
```

## Manual Testing

See the documentation in `../docs/` for manual testing commands and examples.

