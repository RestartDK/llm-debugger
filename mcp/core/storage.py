"""
Storage utilities for saving code context as raw text files.
"""
import os
from datetime import datetime

# Contexts directory for storing code context files
CONTEXTS_DIR = "contexts"

# Ensure contexts directory exists
os.makedirs(CONTEXTS_DIR, exist_ok=True)


def save_code_context(text: str) -> str:
    """
    Save code context as a raw text file with timestamp.
    
    Args:
        text: Raw text content containing code chunks, explanations, and relationships
        
    Returns:
        Success message with filename
    """
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"code_context_{timestamp}.txt"
    filepath = os.path.join(CONTEXTS_DIR, filename)
    
    # Write text to file
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text)
        return f"Code context saved successfully to {filename}"
    except IOError as e:
        return f"Error saving code context: {str(e)}"

