import os
import time
import logging
from pydantic import BaseModel, Field
from typing import List, Optional, Callable
from datetime import datetime
import instructor
import uuid
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class CodeNode(BaseModel):
    id: str = Field(description="The unique identifier for the code node should be a 2-3 word description of the code chunk.")
    code_chunk: str = Field(description="The code chunk of the code node.")
    explanation: str = Field(description="The explanation of the code change should be a 1-2 sentence description of the code chunk.")
    relationships: str = Field(description="The raw text relationship of the code to other code chunks/nodes should be a 1-2 sentence description of the relationship between the code chunk and other code chunks/nodes.")
    filename: str = Field(description="The file the code chunk exists in")
    line_range: str = Field(description="The line range of the code chunk (e.g., '10-25').")

class CodeNodes(BaseModel):
    nodes: List[CodeNode] = Field(description="The list of code nodes.")

class Edge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="The unique identifier for the edge.")
    from_node: str = Field(description="The unique identifier of the from node (focus node).")
    to_node: str = Field(description="The unique identifier of the to node (connected node).")
    relationship_type: str = Field(description="The type of relationship (e.g., calls, imports, data_flow, depends_on, uses, references).")

class EdgesList(BaseModel):
    edges: List[Edge] = Field(description="List of edges from the focus node to other nodes.")


def create_code_nodes(context_dump: str, model: str = "openai/gpt-oss-120b") -> CodeNodes:
    """
    This function accepts a raw text context dump of code chunks, filenames,
    explanations of intended functionality, and relationships between code chunks.

    It returns a list of CodeNode objects, which are created by doing 
    structured output parsing the context dump using instructor wrapped 
    around a groq client running GPT OSS model.
    
    The context dump should contain multiple code chunks in the format:
    - [Code Chunk N] with actual code (5-10 lines)
    - File: <filepath>
    - Lines: <start>-<end>
    - [Explanation] describing what bug might occur
    - [Relationships] describing structural/logical relationships to other chunks
    
    Args:
        context_dump: Raw text containing code chunks, explanations, and relationships
        model: Model to use for extraction (default: "openai/gpt-oss-120b", alternative: "gpt-4o-mini")
        
    Returns:
        CodeNodes object containing a list of CodeNode objects
    """
    logger.info(f"Starting create_code_nodes with model {model}")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set")
    
    client = Groq(api_key=api_key)
    
    system_prompt = """You are an expert code analyzer that extracts structured code node information from context dumps.

Your task is to parse a raw text context dump containing code chunks, filenames, line ranges, explanations, and relationships, then extract each code chunk into a structured CodeNode format.

For each code chunk in the context dump, extract:
1. **id**: A 2-3 word unique identifier describing the code chunk (e.g., "process_data_function", "calculate_totals", "api_handler")
2. **code_chunk**: The actual code lines (5-10 lines) from the [Code Chunk] section
3. **explanation**: The explanation text describing what bug might occur or what the code does
4. **relationships**: The relationships text describing how this code relates to other chunks (structural/logical/data flow)
5. **filename**: The file path from the "File:" line
6. **line_range**: The line range from the "Lines:" line (e.g., "10-25")

Important guidelines:
- Extract ALL code chunks found in the context dump
- Preserve the exact code as written in the [Code Chunk] sections
- Keep explanations concise (1-2 sentences)
- Keep relationships concise (1-2 sentences) focusing on structural/logical connections
- Use the exact filename and line range as provided
- If a code chunk references other chunks in relationships, note those references but keep the focus on structural relationships

The context dump may contain multiple code chunks in sequence. Extract each one into a separate CodeNode."""
    
    user_prompt = f"""Extract all code nodes from the following context dump:

{context_dump}"""
    
    # Wrap client with instructor for structured output
    instructor_client = instructor.from_groq(client)
    
    try:
        response = instructor_client.chat.completions.create(
            model=model,
            response_model=CodeNodes,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        logger.info(f"Successfully created {len(response.nodes)} code nodes")
        return response
    except Exception as e:
        logger.error(f"Failed to create code nodes: {str(e)}")
        raise


def create_code_nodes_with_retry(
    context_dump: str,
    model: str = "openai/gpt-oss-120b",
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    progress_callback: Optional[Callable[[str, str, float], None]] = None
) -> CodeNodes:
    """
    Wrapper function that calls create_code_nodes with retry logic.
    
    Implements exponential backoff retry strategy for handling transient errors
    when calling the Groq API.
    
    Args:
        context_dump: Raw text containing code chunks, explanations, and relationships
        model: Model to use for extraction (default: "openai/gpt-oss-120b", alternative: "gpt-4o-mini")
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        backoff_factor: Multiplier for delay between retries (default: 2.0)
        
    Returns:
        CodeNodes object containing a list of CodeNode objects
        
    Raises:
        Exception: If all retry attempts fail
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            if progress_callback:
                progress_callback("creating_nodes", f"Creating code nodes (attempt {attempt + 1}/{max_retries})...", 0.1 + (attempt * 0.1))
            logger.info(f"Attempting to create code nodes with model {model} (attempt {attempt + 1}/{max_retries})")
            result = create_code_nodes(context_dump, model=model)
            logger.info(f"Successfully created {len(result.nodes)} code nodes")
            if progress_callback:
                progress_callback("creating_nodes", f"Successfully created {len(result.nodes)} code nodes", 0.4)
            return result
        except Exception as e:
            last_exception = e
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(f"All {max_retries} attempts failed. Last error: {str(e)}")
                raise
    
    # This should never be reached, but included for type safety
    if last_exception:
        raise last_exception
    raise Exception("Failed to create code nodes after retries")


def create_edges_for_node(
    focus_node: CodeNode,
    other_nodes: List[CodeNode],
    model: str = "openai/gpt-oss-120b"
) -> List[Edge]:
    """
    Create edges from a focus node to other nodes based on relationships.
    
    Makes one API call to identify all edges FROM the focus node TO other nodes.
    
    Args:
        focus_node: The node to analyze (full information included)
        other_nodes: List of other nodes to check connections to (ID + explanation only)
        model: Model to use for extraction (default: "openai/gpt-oss-120b")
        
    Returns:
        List of Edge objects representing connections from focus_node to other nodes
    """
    logger.info(f"Starting create_edges_for_node for focus node: {focus_node.id} (checking {len(other_nodes)} other nodes)")
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY environment variable is not set")
        raise ValueError("GROQ_API_KEY environment variable is not set")
    
    client = Groq(api_key=api_key)
    
    # Build other nodes context (ID + explanation only)
    other_nodes_context = []
    for node in other_nodes:
        other_nodes_context.append(f"ID: {node.id}\nExplanation: {node.explanation}")
    
    other_nodes_text = "\n\n".join(other_nodes_context)
    
    system_prompt = """You are an expert code relationship analyzer. Your task is to identify directional edges from a focus code node to other code nodes based on their relationships.

CRITICAL: You must produce JSON output that exactly matches the Pydantic schema. The tool will validate your output against this schema, and any deviation will cause errors.

Given:
- A focus node (with full code, explanation, and relationships text)
- A list of other nodes (with ID and explanation only)

Identify all edges FROM the focus node TO other nodes where there is a meaningful relationship.

For each edge, you MUST use these exact field names (the tool validates against this schema):
- **from_node**: The ID of the focus node (the source of the edge)
- **to_node**: The ID of the target node (must match one of the provided node IDs exactly)
- **relationship_type**: The type of relationship (e.g., calls, imports, depends_on, uses, data_flow, references, extends, implements)

Relationship type examples:
- **calls**: Function calls another function
- **imports**: Module/function imports from another
- **depends_on**: Code depends on another chunk
- **uses**: Code uses variables/functions from another
- **data_flow**: Data flows from one chunk to another
- **references**: References another code chunk
- **extends**: Extends or inherits from another
- **implements**: Implements interface/contract from another

IMPORTANT FORMAT REQUIREMENTS:
- Use field names: "from_node", "to_node", "relationship_type" (NOT "source", "target", "relationship", "type")
- The "from_node" must be the focus node's ID
- The "to_node" must exactly match one of the provided node IDs
- Return a list of edges in the format: {"edges": [{"from_node": "...", "to_node": "...", "relationship_type": "..."}, ...]}

Example correct format:
{
  "edges": [
    {
      "from_node": "focus_node_id",
      "to_node": "target_node_id",
      "relationship_type": "calls"
    }
  ]
}

Only create edges where there is a clear relationship indicated by the focus node's relationships text or code structure. If no relationships exist, return an empty list: {"edges": []}."""
    
    user_prompt = f"""Focus Node:
ID: {focus_node.id}
Code: {focus_node.code_chunk}
Explanation: {focus_node.explanation}
Relationships: {focus_node.relationships}

Other Nodes:
{other_nodes_text}

CRITICAL: Identify all edges from the focus node (ID: {focus_node.id}) to other nodes. 

You MUST use these exact field names in your JSON output:
- "from_node": must be "{focus_node.id}" (the focus node ID)
- "to_node": must be one of the node IDs from the "Other Nodes" list above
- "relationship_type": the type of relationship (calls, imports, depends_on, uses, data_flow, references, extends, implements)

DO NOT use field names like "source", "target", "relationship", or "type" - these will cause validation errors.

Example of correct edge format:
{{
  "from_node": "{focus_node.id}",
  "to_node": "target_node_id_from_list_above",
  "relationship_type": "calls"
}}

Create edges only where relationships exist. Return an empty list if no relationships are found."""
    
    # Wrap client with instructor for structured output
    instructor_client = instructor.from_groq(client)
    
    try:
        response = instructor_client.chat.completions.create(
            model=model,
            response_model=EdgesList,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Validate that to_node IDs exist in other_nodes
        valid_node_ids = {node.id for node in other_nodes}
        validated_edges = []
        for edge in response.edges:
            if edge.to_node in valid_node_ids:
                validated_edges.append(edge)
            else:
                logger.warning(f"Invalid edge: to_node '{edge.to_node}' not found in node list. Skipping.")
        
        logger.info(f"Successfully created {len(validated_edges)} edges for node {focus_node.id}")
        return validated_edges
    except Exception as e:
        logger.error(f"Failed to create edges for node {focus_node.id}: {str(e)}")
        raise


def create_edges_from_nodes(
    code_nodes: CodeNodes,
    model: str = "openai/gpt-oss-120b",
    progress_callback: Optional[Callable[[str, str, float], None]] = None
) -> List[Edge]:
    """
    Create edges between all code nodes by analyzing each node's relationships.
    
    Iterates through each node, making one API call per node to identify edges
    FROM that node TO other nodes.
    
    Args:
        code_nodes: CodeNodes object containing list of CodeNode objects
        model: Model to use for extraction (default: "openai/gpt-oss-120b")
        progress_callback: Optional callback(stage, message, progress) for progress updates
        
    Returns:
        List of Edge objects representing all connections between nodes
    """
    all_edges = []
    total_nodes = len(code_nodes.nodes)
    
    logger.info(f"Starting edge generation for {total_nodes} nodes")
    
    if progress_callback:
        progress_callback("creating_edges", f"Starting edge generation for {total_nodes} nodes", 0.4)
    
    for i, focus_node in enumerate(code_nodes.nodes):
        logger.info(f"Processing node {i+1}/{total_nodes}: {focus_node.id}")
        
        # Calculate progress: 40% to 90% for edge generation
        edge_progress = 0.4 + (i / total_nodes) * 0.5
        if progress_callback:
            progress_callback("creating_edges", f"Processing node {i+1}/{total_nodes}: {focus_node.id}", edge_progress)
        
        # Get all other nodes (exclude current focus node)
        other_nodes = [node for j, node in enumerate(code_nodes.nodes) if i != j]
        
        if not other_nodes:
            logger.info(f"No other nodes to connect to for node {focus_node.id}")
            continue
        
        try:
            edges = create_edges_for_node(focus_node, other_nodes, model=model)
            all_edges.extend(edges)
            logger.info(f"Created {len(edges)} edges from node {focus_node.id}")
        except Exception as e:
            logger.error(f"Failed to create edges for node {focus_node.id}: {str(e)}")
            # Continue with other nodes even if one fails
            continue
    
    logger.info(f"Edge generation complete. Total edges created: {len(all_edges)}")
    if progress_callback:
        progress_callback("creating_edges", f"Edge generation complete. Created {len(all_edges)} edges", 0.9)
    return all_edges


def create_edges_from_nodes_with_retry(
    code_nodes: CodeNodes,
    model: str = "openai/gpt-oss-120b",
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    progress_callback: Optional[Callable[[str, str, float], None]] = None
) -> List[Edge]:
    """
    Wrapper function that calls create_edges_from_nodes with retry logic.
    
    Note: This retries the entire edge generation process. Individual node failures
    are handled within create_edges_from_nodes, but if the entire process fails,
    this will retry.
    
    Args:
        code_nodes: CodeNodes object containing list of CodeNode objects
        model: Model to use for extraction (default: "openai/gpt-oss-120b")
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        backoff_factor: Multiplier for delay between retries (default: 2.0)
        
    Returns:
        List of Edge objects representing all connections between nodes
        
    Raises:
        Exception: If all retry attempts fail
    """
    logger.info(f"Starting create_edges_from_nodes_with_retry (max_retries={max_retries}, model={model}, nodes={len(code_nodes.nodes)})")
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to create edges with model {model} (attempt {attempt + 1}/{max_retries})")
            result = create_edges_from_nodes(code_nodes, model=model, progress_callback=progress_callback)
            logger.info(f"Successfully created {len(result)} edges")
            return result
        except Exception as e:
            last_exception = e
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(f"All {max_retries} attempts failed. Last error: {str(e)}")
                raise
    
    # This should never be reached, but included for type safety
    if last_exception:
        raise last_exception
    raise Exception("Failed to create edges after retries")


def generate_code_graph_from_context(
    context_dump: str,
    progress_callback: Optional[Callable[[str, str, float], None]] = None,
    output_dir: str = "contexts"
) -> dict:
    """
    Generate code graph (nodes + edges) from context dump.
    
    Args:
        context_dump: Raw text containing code chunks, explanations, relationships
        progress_callback: Optional callback(stage, message, progress) for progress updates
        output_dir: Directory to save output file (default: "contexts")
        
    Returns:
        dict with keys: "status", "filename", "nodes_count", "edges_count", "message"
    """
    logger.info("Starting generate_code_graph_from_context")
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Output directory ensured: {output_dir}")
        
        # Starting
        if progress_callback:
            progress_callback("starting", "Starting graph generation...", 0.0)
        
        # Create code nodes
        if progress_callback:
            progress_callback("creating_nodes", "Creating code nodes from context dump...", 0.1)
        
        result = create_code_nodes_with_retry(
            context_dump,
            progress_callback=progress_callback
        )
        
        # Create edges from code nodes
        if progress_callback:
            progress_callback("creating_edges", "Creating edges between nodes...", 0.4)
        
        edges = create_edges_from_nodes_with_retry(
            result,
            progress_callback=progress_callback
        )
        
        # Convert to dicts for JSON serialization
        nodes_dict = result.model_dump()
        edges_dict = [edge.model_dump() for edge in edges]
        
        # Create combined output with nodes and edges
        combined_output = {
            "nodes": nodes_dict["nodes"],
            "edges": edges_dict
        }
        
        # Generate filename: YYYY-MM-DD_HH-MM.json
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Saving
        if progress_callback:
            progress_callback("saving", f"Saving graph to {filename}...", 0.95)
        
        # Save to JSON file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(combined_output, f, indent=4, ensure_ascii=False)
        
        # Complete
        if progress_callback:
            progress_callback("complete", "Graph generation complete. Check the UI.", 1.0)
        
        result_dict = {
            "status": "completed",
            "message": "Graph generation complete. Check the UI.",
            "filename": filename,
            "nodes_count": len(result.nodes),
            "edges_count": len(edges)
        }
        logger.info(f"Successfully completed generate_code_graph_from_context: {result_dict}")
        return result_dict
        
    except Exception as e:
        error_msg = f"Error generating graph: {str(e)}"
        logger.error(f"Failed generate_code_graph_from_context: {error_msg}", exc_info=True)
        if progress_callback:
            progress_callback("error", error_msg, 0.0)
        return {
            "status": "error",
            "message": error_msg,
            "filename": None,
            "nodes_count": 0,
            "edges_count": 0
        }


if __name__ == "__main__":
    context_dump = """
dummy
    """
    
    # Simple progress callback for testing
    def test_progress_callback(stage: str, message: str, progress: float):
        print(f"[{progress:.1%}] {stage}: {message}")
    
    # Generate graph using the new function
    result = generate_code_graph_from_context(
        context_dump,
        progress_callback=test_progress_callback
    )
    
    print("\n" + "=" * 80)
    print("RESULT:")
    print("=" * 80)
    print(json.dumps(result, indent=4))


