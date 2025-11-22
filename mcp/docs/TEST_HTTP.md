# Testing MCP Server HTTP Endpoints

The MCP server is deployed on a VPS and accessible via HTTP. Use these commands to test it.

## Quick Test Commands

Replace `YOUR_VPS_URL` with your actual VPS URL (e.g., `http://your-domain.com` or `http://123.45.67.89:8000`)

### 1. Health Check
```bash
curl -v http://YOUR_VPS_URL/health
```

Expected response:
```json
{"status":"ok","service":"Debug Context MCP Server"}
```

### 2. Root Endpoint
```bash
curl -v http://YOUR_VPS_URL/
```

Expected response: JSON with server info and available endpoints

### 3. Documentation
```bash
curl -v http://YOUR_VPS_URL/api/documentation
```

### 4. Project Context
```bash
curl -v http://YOUR_VPS_URL/api/project/context
```

### 5. Submit Code Changes (Structured)
```bash
curl -v -X POST http://YOUR_VPS_URL/api/changes/submit \
  -H "Content-Type: application/json" \
  -d '{
    "format_type": "structured",
    "content": {
      "old_code": "def old_function(): pass",
      "new_code": "def new_function(): return True"
    },
    "file_path": "test.py",
    "line_numbers": {"start": 1, "end": 5},
    "relationships": {"affected_files": []}
  }'
```

### 6. Submit Code Changes (Diff Format)
```bash
curl -v -X POST http://YOUR_VPS_URL/api/changes/submit \
  -H "Content-Type: application/json" \
  -d '{
    "format_type": "diff",
    "content": "--- a/test.py\n+++ b/test.py\n@@ -1,3 +1,3 @@\n-def old():\n+def new():\n     pass"
  }'
```

### 7. Get Chunk Context
```bash
curl -v -X POST http://YOUR_VPS_URL/api/debug/chunk-context \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "test.py",
    "line_numbers": {"start": 1, "end": 10}
  }'
```

### 8. SSE Endpoint (MCP over HTTP)
```bash
curl -v http://YOUR_VPS_URL/sse
```

## Using the Test Script

Run the automated test script:

```bash
cd llm-debugger/mcp
./test_http.sh http://YOUR_VPS_URL
```

Or test locally if running on your machine:
```bash
./test_http.sh http://localhost:8000
```

## Expected Results

All endpoints should return HTTP 200 status codes with JSON responses.

If you see connection errors:
- Check if the server is running on the VPS
- Verify the URL/port is correct
- Check firewall settings
- Verify the service is listening on the correct interface (0.0.0.0)

## Troubleshooting

### Connection Refused
- Server might not be running
- Wrong port number
- Firewall blocking the connection

### 404 Not Found
- Check the URL path
- Verify the server is running the correct version

### 500 Internal Server Error
- Check server logs on VPS
- Verify dependencies are installed
- Check file permissions for storage files

