# LLM Debugger

## Problem Statement Alignment

**Core Insight:** Current AI coding agents treat code as monolithic text and only use post-execution feedback (pass/fail, error messages). This mirrors the LDB paper's finding that LLMs struggle with complex logic flows because they lack visibility into *how* code executes, not just *whether* it works.

**Our Solution:** Bring runtime execution transparency to agentic coding workflows by visualizing Control Flow Graphs, tracking intermediate variable states, and pinpointing exact failure points—giving LLMs (and developers) surgical precision for debugging.

**Product:** A web-based debugging visualization tool that connects to your codebase via an MCP server and provides real-time CFG analysis for LLM-assisted debugging.

**How it works:**

1. Connect to any codebase via MCP server integration
2. When debugging is triggered, the backend generates a CFG and instruments the code
3. Run the code with test cases, capturing variable states at each basic block
4. Visualize the CFG with color-coded nodes (green = consistent, red = failure points)
5. Export the failure analysis as structured context for the LLM to target fixes

**Target Users:** Developers already comfortable with agentic workflows (Cursor, Claude Code, Windsurf users) who want better visibility into *why* their AI agent is struggling with a bug.

**Long-term Potential (Impact):**

- Plugin ecosystem for existing AI coding tools (Cursor, Cline, Continue, etc.)
- Becomes the "debugging layer" that any AI coding agent can call
- Could evolve into a standard protocol for LLM-aware debugging across the industry

**Strengths for judging:**

- High impact potential as infrastructure for the AI coding ecosystem
- Clear differentiation from existing tools
- Addresses the exact problem statement (semantic awareness, reasoning across code)

## Frontend plan

- The user wants to see the current control flow graph that is being edited from the backend to be debugged
- They want to see what files that are relevant
- They want to see every node in the CFG with their relevant code snippet
- They want to see what are the actual intermediate states are when debugging
  - The outputs of what each code snippet in the CFG is creating at runtime
- Then we want to have each node that has a pending state of it working, then it shows a state of whether it passed or failed the check at that point in the CFG
  - If it fails, then show an error with the reason for it from the llm
- They need to see what the current status is, is the agent finding more things? (less important)

## Backend plan

- Set up MCP/FASTAPI and connect to coding agent (cursor)
- Get mock inputs from coding agent saved as files and send to MCP with test python script
- Create Agent workflow that is triggered in MCP/API and run in same container in coolify
- Create data schema to connect to frontend
- Create mock data API routes to have immediate connectivity for frontend iteration

## TODO

- [ ]  First get it done with the basic frontend normal api routes, and backend, with using the llm debugger, no applying of the code on the cursor
- [ ]  Add feature for reasoning for problem
- [ ]  Add the feature for applying of the code in the editor
- [ ]  Fix search to move from cursor to our own implementation
- [ ]  Maybe use markdown for runtime state inspector and problems
- [ ]  Autonomously fix the bug by providing a loop with the agent once the debugger has found a result
