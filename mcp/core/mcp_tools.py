"""
MCP tool functions for the debug context server.
"""
from .storage import save_code_context


def submit_code_context(text: str) -> str:
    """
    Submit code context as raw text.
    
    Args:
        text: Raw text containing code chunks, explanations, and relationships
        
    Returns:
        Success message with filename
    """
    return save_code_context(text)

