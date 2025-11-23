<!-- 3710f5b5-36bf-419a-9ae1-d5b8a03caa58 0847fb9b-8fd8-4675-ac08-55b456eb5254 -->
## Stabilize CFG generation and analysis pipeline

### Goals

- **Make `/get_control_flow_diagram` deterministic and independent of LLM-generated tests**, so the frontend always gets a stable CFG (nodes/edges) even when tests are bad.
- **Fix the `asyncio` event-loop/threading problem in `/execute_test_cases`**, so the analysis pipeline runs reliably without cross-loop errors.
- **Handle "no executable blocks" cases gracefully** in the analysis path so the UI still shows a CFG with clear error context.

### Steps

- **1. Make CFG generation purely static**
- Extract or implement a helper (e.g. `build_static_cfg_from_blocks`) in `mcp/core/llm_workflow_orchestrator.py` that takes `BasicBlock`s (from `get_dummy_blocks` or real blocks) and builds `nodes` and `edges` without running tests or calling Gemini.
- Update `mcp/api/control_flow.py:get_control_flow_diagram` to call this helper directly, using `get_dummy_blocks()` only, and remove the call to `run_generated_test_through_tracer_and_analyze`.
- Ensure the helper sets each node's initial `status` to `'pending'` so it aligns with the frontend's visual states.

- **2. Tidy up `build_debugger_ui_payload` for dynamic analysis**
- Keep `build_debugger_ui_payload` focused on turning a full `LlmDebugRunResult` (with runtime states) into rich `steps`, `problems`, `nodes`, and `edges` for `/execute_test_cases` responses.
- Confirm that node/step status mapping (`succeeded`/`failed`) remains correct for the dynamic analysis path.

- **3. Improve behavior when no blocks execute**
- In `run_generated_test_through_tracer_and_analyze`, change the `if not block_infos or not runtime_states` branch to **preserve the static blocks** (from `block_lookup`) instead of returning `blocks=[]`.
- In `build_debugger_ui_payload`, detect the case where there are blocks but no runtime states and:
  - Set node statuses to a neutral or error state (e.g. `'pending'` or `'failed'`) and
  - Surface the `error_info` / `debug_analysis.failed_test.actual` message in a way the frontend can display (e.g. as a global problem or analysis banner).

- **4. Fix the `asyncio` event loop/threading error in `/execute_test_cases`**
- In `mcp/main.py`, simplify the `/execute_test_cases` endpoint so it does **not** call `execute_test_cases` via `asyncio.to_thread`; instead, call the function synchronously from the FastAPI handler (or, if you make it async, run it on the main event loop directly).
- Verify that no code in the analysis pipeline (`LlmDebugAgent`, `pydantic-ai`, etc.) is trying to reuse `asyncio` primitives across different event loops or threads.
- If blocking is a concern, consider a future improvement with a proper background worker/queue, but avoid mixing `to_thread` with event-loop-bound primitives.

- **5. Harden test generation to avoid trivial `NameError` tests**
- Review the prompt in `core/test_generation_llm.py` and explicitly instruct Gemini to always:
  - Call the target function, and
  - Assign its return value to a `result` variable before any assertions.
- Optionally, add a simple post-filter that discards generated tests which do not contain a `result =` assignment and a call to the target function in the code snippet.

- **6. Manual and automated checks**
- Manually hit `/get_control_flow_diagram` a few times and confirm `nodes`/`edges` are stable and non-empty, regardless of LLM output.
- Trigger `/execute_test_cases` from the frontend and confirm there are no `asyncio` loop errors in the logs, that the diagram remains rendered, and that failure cases show meaningful error context instead of an empty graph.
- Optionally add a simple HTTP test (in `mcp/tests/test_http.sh` or a Python test) that asserts the CFG endpoint always returns at least one node and that `/execute_test_cases` returns the full payload shape, even when trace entries are zero.

### To-dos

- [ ] Create a static CFG builder helper in mcp/core/llm_workflow_orchestrator.py and refactor mcp/api/control_flow.py:get_control_flow_diagram to use it instead of running tests.
- [ ] Confirm and, if needed, adjust build_debugger_ui_payload so it only depends on LlmDebugRunResult for dynamic analysis and keeps status mapping correct.
- [ ] Change run_generated_test_through_tracer_and_analyze and build_debugger_ui_payload to preserve blocks and surface errors when no blocks are executed, instead of returning an empty CFG.
- [ ] Remove asyncio.to_thread usage around execute_test_cases in mcp/main.py and ensure the analysis pipeline runs in a single event loop without cross-thread asyncio primitives.
- [ ] Tighten the LLM test-generation prompt and optionally add basic static checks to avoid emitting tests that don’t call the target or define result.
- [ ] Manually and/or via tests verify that /get_control_flow_diagram always returns a stable, non-empty CFG and that /execute_test_cases runs without asyncio errors, returning useful payloads even on test failures.