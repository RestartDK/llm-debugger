"""
Debug fix instructions handling.
"""


def send_debugger_response(data: dict) -> dict:
    """
    Accept debugger feedback payloads (e.g., user-selected fixes) and echo them.
    """

    return {
        "status": "ok",
        "echo": data,
    }

