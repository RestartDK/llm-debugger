# Connection ID Research for Cursor MCP SSE

## Problem

Cursor is POSTing to `/sse` but not providing `connection_id` in headers or query parameters, causing progress updates to fail.

## Research Findings

### Standard MCP SSE Pattern

1. **Client opens SSE stream**: `GET /sse?connection_id=<uuid>` or `GET /sse` (server generates ID)
2. **Server responds**: Sends `connection_id` in SSE stream header or initial message
3. **Client sends requests**: `POST /sse/message` with `X-Connection-ID` header
4. **Server queues responses**: Uses `connection_id` to route responses to correct SSE stream

### Cursor's Behavior

Based on logs, Cursor appears to:
- POST directly to `/sse` (not `/sse/message`)
- Not include `connection_id` in headers or query params
- May be using a different connection tracking mechanism

### Possible Solutions

#### Option 1: Track by Client IP/Session (Fallback)
- Use client IP address + User-Agent as connection identifier
- Store mapping: `(ip, user_agent) -> connection_id`
- When POST arrives without connection_id, look up by IP/UA

#### Option 2: Check Request Body
- Some implementations send `connection_id` in JSON body
- Extract from `body.get("connection_id")` or `body.get("params", {}).get("connection_id")`

#### Option 3: Single Active Connection
- If only one SSE connection exists, use it automatically
- Simple fallback for single-client scenarios

#### Option 4: Cookie-Based Tracking
- Set cookie when SSE connection is established
- Read cookie from POST requests

## Recommended Implementation

Use a **hybrid approach**:
1. **Primary**: Extract from headers (`X-Connection-ID`, `x-connection-id`)
2. **Secondary**: Extract from query params (`connection_id`)
3. **Tertiary**: Extract from request body (`connection_id` field)
4. **Fallback**: Use first available connection if only one exists
5. **Last resort**: Track by client IP + User-Agent

## Implementation Notes

- Log all connection_id extraction attempts for debugging
- Warn when connection_id is missing but don't fail
- Support multiple concurrent connections properly
- Clean up stale connections periodically

