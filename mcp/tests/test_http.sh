#!/bin/bash

# Test script for MCP Debug Context Server HTTP endpoints
# Usage: ./test_http.sh <BASE_URL>
# Example: ./test_http.sh http://your-vps-domain.com
#          ./test_http.sh http://localhost:8000

BASE_URL="${1:-http://localhost:8000}"

echo "=========================================="
echo "Testing MCP Debug Context Server"
echo "Base URL: $BASE_URL"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to test an endpoint
test_endpoint() {
    local method=$1
    local endpoint=$2
    local description=$3
    local data=$4
    
    echo -e "${YELLOW}Testing: $description${NC}"
    echo "  $method $BASE_URL$endpoint"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$BASE_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$BASE_URL$endpoint")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo -e "  ${GREEN}✓ PASS${NC} (HTTP $http_code)"
        echo "  Response: $(echo "$body" | head -c 200)..."
        ((TESTS_PASSED++))
    else
        echo -e "  ${RED}✗ FAIL${NC} (HTTP $http_code)"
        echo "  Response: $body"
        ((TESTS_FAILED++))
    fi
    echo ""
}

# Test 1: Health check
test_endpoint "GET" "/health" "Health Check"

# Test 2: Root endpoint
test_endpoint "GET" "/" "Root Endpoint"

# Test 3: Documentation endpoint
test_endpoint "GET" "/api/documentation" "Get Documentation"

# Test 4: Project context
test_endpoint "GET" "/api/project/context" "Get Project Context"

# Test 5: Submit changes (structured format)
test_endpoint "POST" "/api/changes/submit" "Submit Code Changes (Structured)" \
'{
  "format_type": "structured",
  "content": {
    "old_code": "def old_function(): pass",
    "new_code": "def new_function(): return True"
  },
  "file_path": "test.py",
  "line_numbers": {"start": 1, "end": 5},
  "relationships": {"affected_files": []}
}'

# Test 6: Submit changes (diff format)
test_endpoint "POST" "/api/changes/submit" "Submit Code Changes (Diff)" \
'{
  "format_type": "diff",
  "content": "--- a/test.py\n+++ b/test.py\n@@ -1,3 +1,3 @@\n-def old():\n+def new():\n     pass"
}'

# Test 7: Get chunk context
test_endpoint "POST" "/api/debug/chunk-context" "Get Chunk Context" \
'{
  "file_path": "test.py",
  "line_numbers": {"start": 1, "end": 10}
}'

# Test 8: SSE endpoint (should return SSE headers)
echo -e "${YELLOW}Testing: SSE Endpoint${NC}"
echo "  GET $BASE_URL/sse"
sse_response=$(curl -s -I "$BASE_URL/sse" 2>&1)
if echo "$sse_response" | grep -q "text/event-stream\|Content-Type.*event-stream"; then
    echo -e "  ${GREEN}✓ PASS${NC} (SSE headers present)"
    ((TESTS_PASSED++))
else
    echo -e "  ${RED}✗ FAIL${NC} (SSE headers not found)"
    echo "  Response headers: $sse_response"
    ((TESTS_FAILED++))
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Check output above.${NC}"
    exit 1
fi

