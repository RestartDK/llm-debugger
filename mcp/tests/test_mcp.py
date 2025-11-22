#!/usr/bin/env python3
"""
Test script to verify MCP server is working correctly.
This script tests the MCP server by calling it via stdio.
"""
import json
import subprocess
import sys
import os

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# MCP main.py is one level up from tests/
MCP_DIR = os.path.dirname(SCRIPT_DIR)

def send_mcp_request(method, params=None, request_id=1):
    """Send an MCP JSON-RPC request via stdio."""
    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
    }
    if params:
        request["params"] = params
    
    return json.dumps(request) + "\n"

def test_mcp_server():
    """Test the MCP server by sending initialization and tool listing requests."""
    print("Testing MCP Server Connection...")
    print("=" * 50)
    
    # Start the MCP server process
    mcp_script = os.path.join(MCP_DIR, "main.py")
    python_cmd = sys.executable
    
    try:
        # Start the process
        process = subprocess.Popen(
            [python_cmd, mcp_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=MCP_DIR
        )
        
        # Send initialize request
        print("\n1. Sending initialize request...")
        init_request = send_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        )
        process.stdin.write(init_request)
        process.stdin.flush()
        
        # Read response
        response_line = process.stdout.readline()
        if response_line:
            response = json.loads(response_line.strip())
            print(f"   Response: {json.dumps(response, indent=2)}")
        else:
            print("   ERROR: No response received")
            return False
        
        # Send initialized notification
        print("\n2. Sending initialized notification...")
        initialized = send_mcp_request("notifications/initialized")
        process.stdin.write(initialized)
        process.stdin.flush()
        
        # Send tools/list request
        print("\n3. Requesting tools list...")
        tools_request = send_mcp_request("tools/list")
        process.stdin.write(tools_request)
        process.stdin.flush()
        
        # Read tools response
        tools_response_line = process.stdout.readline()
        if tools_response_line:
            tools_response = json.loads(tools_response_line.strip())
            print(f"   Response: {json.dumps(tools_response, indent=2)}")
            
            if "result" in tools_response and "tools" in tools_response["result"]:
                tools = tools_response["result"]["tools"]
                print(f"\n   ✓ Found {len(tools)} tools:")
                for tool in tools:
                    print(f"     - {tool.get('name', 'unknown')}: {tool.get('description', 'no description')}")
                return True
            else:
                print("   ERROR: Invalid tools response format")
                return False
        else:
            print("   ERROR: No tools response received")
            return False
            
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        try:
            process.stdin.close()
            process.terminate()
            process.wait(timeout=2)
        except:
            pass

def test_tool_execution():
    """Test executing a specific MCP tool."""
    print("\n" + "=" * 50)
    print("Testing Tool Execution...")
    print("=" * 50)
    
    mcp_script = os.path.join(MCP_DIR, "main.py")
    python_cmd = sys.executable
    
    try:
        process = subprocess.Popen(
            [python_cmd, mcp_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=MCP_DIR
        )
        
        # Initialize
        init_request = send_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        )
        process.stdin.write(init_request)
        process.stdin.flush()
        process.stdout.readline()  # Read init response
        
        # Send initialized
        initialized = send_mcp_request("notifications/initialized")
        process.stdin.write(initialized)
        process.stdin.flush()
        
        # Test get_mcp_documentation_mcp tool
        print("\n4. Testing get_mcp_documentation_mcp tool...")
        tool_request = send_mcp_request(
            "tools/call",
            {
                "name": "get_mcp_documentation_mcp",
                "arguments": {}
            },
            request_id=2
        )
        process.stdin.write(tool_request)
        process.stdin.flush()
        
        tool_response_line = process.stdout.readline()
        if tool_response_line:
            tool_response = json.loads(tool_response_line.strip())
            print(f"   Response: {json.dumps(tool_response, indent=2)}")
            if "result" in tool_response:
                print("   ✓ Tool executed successfully!")
                return True
            else:
                print("   ERROR: Tool execution failed")
                return False
        else:
            print("   ERROR: No tool response received")
            return False
            
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            process.stdin.close()
            process.terminate()
            process.wait(timeout=2)
        except:
            pass

if __name__ == "__main__":
    print("MCP Server Test Suite")
    print("=" * 50)
    
    # Test 1: Basic connection and tool listing
    success1 = test_mcp_server()
    
    # Test 2: Tool execution
    success2 = test_tool_execution()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("✓ All tests passed! MCP server is working correctly.")
        sys.exit(0)
    else:
        print("✗ Some tests failed. Check the output above for details.")
        sys.exit(1)

