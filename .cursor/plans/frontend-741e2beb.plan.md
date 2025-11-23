<!-- 741e2beb-e5fe-4131-944a-5ba3294219e0 f4a448e9-e5de-4d47-8239-b5f8ca93f3a8 -->
# Frontend–Backend Integration Plan (No Explicit User Feedback)

### 1. Align on data contracts between backend and frontend

- **Inspect existing payload builder**: Confirm the exact shapes that `build_debugger_ui_payload` returns (keys for `steps`, `problems`, `nodes`, `edges`, `analysis`) in `mcp/core/llm_workflow_orchestrator.py`.
- **Define shared TypeScript interfaces**: In `client/src/lib/types.ts`, add/confirm interfaces for the full debugger payload (e.g. `DebuggerPayload` with `steps: RuntimeStep[]`, `problems: Problem[]`, `nodes: Node<CfgNodeData>[]`, `edges: Edge[]`, `analysis: unknown`).
- **Decide URL base**: Choose how the frontend reaches the backend (e.g. `VITE_API_BASE_URL=http://localhost:8000`) and document this in `client/README.md`.

### 2. Backend: Make `/get_control_flow_diagram` return UI-friendly CFG from dummy pipeline

- **Replace hardcoded graph**: In `mcp/main.py`, change `get_control_flow_diagram_endpoint` to call `api.get_control_flow_diagram()` instead of returning `HARDCODED_CODE_GRAPH` from `mcp/dummy_cfg.py`.
- **Ensure response shape**: Confirm that `api.get_control_flow_diagram()` returns a dict with `nodes` and `edges` already shaped like the frontend expects (`id`, `type: 'cfgNode'`, `position`, `data: CfgNodeData`, `source`, `target`). If needed, adapt its return value to match the existing `initialNodes`/`initialEdges` structure used in `mockData.ts`.
- **Keep dummy-only scope**: Leave the underlying call using `get_dummy_sources()` and `get_dummy_blocks()` so this endpoint remains a non-destructive, demo-only CFG builder.
- **Add simple health logging**: Log when the endpoint is hit and how many nodes/edges are returned to aid debugging.

### 3. Backend: Keep `/execute_test_cases` as the single “run tests + LLM analysis” entrypoint

- **Confirm contract**: Verify that `mcp/api/test_cases.py:execute_test_cases` returns exactly the `build_debugger_ui_payload(run_result)` dict with `steps`, `problems`, `nodes`, `edges`, `analysis`.
- **Support optional custom sources**: Ensure that if `sources` are omitted in the POST body, the function falls back to `get_dummy_sources()` (already coded) so the frontend can initially call it with just `task_description`.
- **Document minimal request body**: In `mcp/docs/TEST_HTTP.md` or a new short doc, specify that the frontend should send `{ "task_description": "..." }` (and optionally `sources`) to this endpoint.
- **No user feedback dependency**: Confirm that `execute_test_cases` does not consume any user labels; all node statuses and problem explanations must come from `run_generated_test_through_tracer_and_analyze` + `build_debugger_ui_payload` alone.

### 4. Backend: Background “fix generation” hook (no UI involvement)

- **Clarify responsibility**: Keep `/send_debugger_response` as a backend automation hook that the UI does not call directly.
- **Automatic invocation (optional enhancement)**:
- Option A (simple): Leave `send_debugger_response` only for manual/developer use for now.
- Option B (more automatic): After `execute_test_cases` detects problems (non-empty `problems` or failing blocks), asynchronously call `apply_suggested_fixes_to_source` by constructing an `instructions` string from the `analysis` field and problem list, then forward it to the MCP tool. Do not change this plan until you’re ready to have the system propose real edits.
- **Safety constraints**: Ensure `apply_suggested_fixes_to_source` remains conservative (only touching files and chunks described in its instructions) and that background fix application is opt‑in via configuration (e.g. env flag `ENABLE_AUTO_FIX=false` by default).

### 5. Frontend: Introduce a typed API client layer

- **Create `client/src/lib/api.ts`** with:
- `API_BASE_URL` resolved from `import.meta.env.VITE_API_BASE_URL`.
- A helper `request<T>(path: string, options?: RequestInit): Promise<T>` that handles JSON, errors, and timeouts.
- `fetchControlFlow(): Promise<{ nodes: Node<CfgNodeData>[]; edges: Edge[] }>` calling `GET /get_control_flow_diagram`.
- `executeTestCases(body: { task_description: string; sources?: { file_path: string; code: string }[] }): Promise<DebuggerPayload>` calling `POST /execute_test_cases`.
- **Error handling policy**: Centralize HTTP error mapping (e.g. network failures vs 4xx/5xx) and expose user‑friendly messages for the UI to consume.

### 6. Frontend: Replace mock CFG and runtime data with backend data

- **State changes in `client/src/App.tsx`**:
- Replace static `mockSteps`, `mockProblems`, `initialNodes`, `initialEdges` with state variables `steps`, `problems`, `nodes`, `edges` initialised to empty arrays.
- Add loading/error state for CFG and analysis (`cfgLoading`, `cfgError`, `analysisLoading`, `analysisError`).
- **On initial load**:
- In a `useEffect`, call `fetchControlFlow()`.
- On success: set `nodes`, `edges` and derive a default `activeNodeId` from the first node; keep `steps`/`problems` empty until tests are run.
- On failure: set `cfgError` and display a small error banner in place of the graph.
- **Wire components to dynamic data**:
- Pass `nodes`/`edges` into `CfgCanvas` instead of `initialNodes`/`initialEdges` mocks.
- Pass `steps` and `problems` from state into `LeftPanel` instead of mock versions.

### 7. Frontend: Add a “Run analysis” control that calls `/execute_test_cases`

- **UI placement**: Add a button (e.g. top‑right above `CfgCanvas`) labeled “Run analysis” or “Generate tests & analysis”.
- **On click behaviour**:
- Set `analysisLoading=true` and `analysisError=null`.
- Call `executeTestCases({ task_description: "Investigate dummy ecommerce pipeline" })`.
- On success:
- Update `steps`, `problems`, `nodes`, `edges` from the payload.
- If `problems.length > 0`, focus on the first problem (`activeNodeId = problem.blockId`, `activeStepId = problem.stepId`); otherwise focus on the last step.
- Leave all node/problem explanation text as returned from the backend; the user does not label anything.
- On error: set `analysisError` and surface a non‑intrusive message in the left panel or above the graph.
- **Optional automation**: To get even closer to your sketch, auto‑trigger this “Run analysis” once the CFG has loaded (e.g. another `useEffect` that fires when `nodes` first become non‑empty), but still keep the button for manual re‑runs.

### 8. Frontend: Visual consistency between CFG and runtime/problems

- **Node highlighting**:
- Keep the existing `activeNodeId`/`activeStepId` syncing logic in `App.tsx`.
- Ensure that when nodes/steps are replaced from backend payloads, the selection is recomputed (e.g. default to first failing node or first node if none failed).
- **Status styling**:
- Ensure `CfgNode` reads `data.status` and visually distinguishes failed vs succeeded blocks (colour, border, or icon), using only backend‑supplied status from `build_debugger_ui_payload`.
- In `RuntimeInspector`, use `problems` to display warnings and errors per step (already supported via `hasWarning` logic; confirm mapping still works with live data).
- **No feedback UI**:
- Confirm there are no controls that ask the user to label nodes as correct/incorrect; if any were added before, remove them or hide them behind a dev flag.

### 9. Testing and validation

- **Backend tests**:
- Extend or add tests (similar to `mcp/tests/test_ldb_methodology_multi_file.py`) that call `get_control_flow_diagram()` and `execute_test_cases()` directly, asserting:
- Non‑empty `nodes` and `edges` with expected keys.
- `steps` and `problems` are present and structurally valid.
- Optionally add a FastAPI test using `TestClient` to ensure HTTP responses have the right shapes and status codes.
- **Frontend tests / manual checks**:
- Manually verify that:
- Opening the app fetches and shows a CFG without errors.
- Clicking “Run analysis” updates the left panel and canvas with steps and problems.
- No manual feedback is required for nodes; the UI simply visualizes backend results.
- **End‑to‑end sanity**:
- Run the backend server and `client` dev server together; step through the full flow: open app → diagram loads → run analysis → see nodes marked as failing and `ProblemsList` populated.

### 10. Documentation and configuration

- **Update backend docs**: In `mcp/docs/TEST_HTTP.md` (or similar), document:
- `GET /get_control_flow_diagram`: purpose, response shape.
- `POST /execute_test_cases`: minimal request, response shape, and that it does LLM analysis automatically.
- **Update frontend README**: Briefly describe environment variables, how to start both servers, and the expected end‑to‑end flow for a user (“Open app, see CFG, click Run analysis, inspect problems; no manual labeling step”).
- **Flag future work**: Note that `/send_debugger_response` and automatic fix application are backend features that can be enabled later, without requiring changes to the core visualization flow described above.

### To-dos

- [ ] Confirm and document the JSON contracts between backend payloads (build_debugger_ui_payload, get_control_flow_diagram) and frontend TypeScript types.
- [ ] Update GET /get_control_flow_diagram in mcp/main.py to call api.get_control_flow_diagram() and return UI-ready nodes/edges based on the dummy pipeline.
- [ ] Verify and, if necessary, refine POST /execute_test_cases so it returns the full debugger UI payload (steps, problems, nodes, edges, analysis) without requiring user feedback.
- [ ] Create a typed API client in client/src/lib/api.ts to call /get_control_flow_diagram and /execute_test_cases using shared interfaces.
- [ ] Refactor App.tsx and related components to replace mock CFG and runtime data with live data from the backend, including loading/error states.
- [ ] Add a Run analysis control in the UI that triggers executeTestCases, updates steps/problems/nodes/edges, and synchronizes active selections without any user feedback inputs.
- [ ] Ensure CFG nodes, runtime inspector, and problems list render consistent statuses and selections based solely on backend-provided data.
- [ ] Add/update tests and documentation covering the new endpoints, frontend integration, and the no-user-feedback flow.