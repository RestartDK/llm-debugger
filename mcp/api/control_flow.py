"""
Control flow diagram generation.
"""

import os
import json
import re
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def get_most_recent_context_json(contexts_dir: str = "contexts") -> Optional[dict]:
    """
    Read the most recent control flow graph JSON file from the contexts directory.
    
    Only considers files matching the timestamp pattern YYYY-MM-DD_HH-MM.json.
    Returns the parsed JSON as a dictionary.
    
    Args:
        contexts_dir: Directory containing context JSON files (default: "contexts")
        
    Returns:
        Dictionary containing the graph data (nodes and edges), or None if file cannot be read
        
    Raises:
        Does not raise exceptions - returns None on error
    """
    logger.info(f"Fetching most recent context JSON from {contexts_dir}/ folder")
    
    try:
        # Check if directory exists
        if not os.path.exists(contexts_dir):
            error_msg = f"Error: Contexts directory '{contexts_dir}' does not exist"
            logger.error(error_msg)
            return None
        
        # List all files in the directory
        all_files = os.listdir(contexts_dir)
        logger.info(f"Found {len(all_files)} files in {contexts_dir}/")
        
        # Filter files matching timestamp pattern YYYY-MM-DD_HH-MM.json
        timestamp_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.json$')
        timestamped_files = [f for f in all_files if timestamp_pattern.match(f)]
        
        if not timestamped_files:
            error_msg = f"Error: No context JSON files found in {contexts_dir}/ folder. Expected files matching pattern YYYY-MM-DD_HH-MM.json"
            logger.warning(error_msg)
            return None
        
        logger.info(f"Found {len(timestamped_files)} timestamped context JSON files")
        
        # Parse timestamps and sort by most recent first
        def parse_timestamp(filename: str) -> datetime:
            """Extract timestamp from filename (YYYY-MM-DD_HH-MM.json)"""
            try:
                timestamp_str = filename.replace('.json', '')
                return datetime.strptime(timestamp_str, '%Y-%m-%d_%H-%M')
            except ValueError as e:
                logger.warning(f"Failed to parse timestamp from filename '{filename}': {e}")
                return datetime.min  # Put unparseable files at the end
        
        # Sort by timestamp (most recent first)
        sorted_files = sorted(timestamped_files, key=parse_timestamp, reverse=True)
        most_recent_file = sorted_files[0]
        most_recent_timestamp = parse_timestamp(most_recent_file)
        
        logger.info(f"Most recent context JSON file: {most_recent_file} (timestamp: {most_recent_timestamp})")
        
        # Read and parse the most recent JSON file
        filepath = os.path.join(contexts_dir, most_recent_file)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)
            
            nodes_count = len(graph_data.get("nodes", []))
            edges_count = len(graph_data.get("edges", []))
            logger.info(f"Retrieved graph from {most_recent_file} (nodes: {nodes_count}, edges: {edges_count})")
            
            return graph_data
            
        except json.JSONDecodeError as e:
            error_msg = f"Error: Failed to parse JSON from file '{most_recent_file}'. {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None
        except IOError as e:
            error_msg = f"Error: Failed to read context JSON file '{most_recent_file}'. {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None
            
    except Exception as e:
        error_msg = f"Error fetching context JSON: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return None


def get_control_flow_diagram() -> dict:
    """
    Return nodes/edges describing the CFG from the most recent context JSON file.
    
    Reads the most recent JSON file from the contexts/ folder that matches
    the timestamp pattern YYYY-MM-DD_HH-MM.json.
    """
    graph_data = get_most_recent_context_json()
    
    if graph_data is None:
        # Fallback to empty graph if no context file found
        logger.warning("No context JSON file found, returning empty graph")
        return {
            "nodes": [],
            "edges": []
        }
    
    return graph_data

