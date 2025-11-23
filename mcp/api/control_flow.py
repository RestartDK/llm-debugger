"""
Control flow diagram generation.
"""

from core.dummy_cfg import get_dummy_blocks, get_dummy_sources
from core.llm_workflow_orchestrator import build_static_cfg_from_blocks


def get_control_flow_diagram() -> dict:
    """
    Return nodes/edges describing the CFG derived from the dummy ecommerce flow.
    """

    blocks = get_dummy_blocks()
    sources = get_dummy_sources()
    return build_static_cfg_from_blocks(blocks, sources)

