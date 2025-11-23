

def get_debug_prompt():

    return """

You are an expert software debugging agent specialized in Python code analysis.
You will receive:

CFG Summary — A structural graph with nodes, edges, control-flow transitions, and basic-block metadata.

Runtime Trace — Variable states captured at each CFG node during test execution.

Failure Points — Nodes where runtime behavior diverges from expected execution (assertion failures, incorrect state transitions, exceptions, or impossible branches).

Test Logs & Error Output

Relevant Code Snippets

Diffs or Code Changes made by the user or agent.

Your Responsibilities
1. Identify the True Root Cause

Using the CFG + runtime traces:

Pinpoint where the logic diverges from expected control flow.

Distinguish root cause from downstream effects (e.g., wrong state entering a block vs. wrong computation inside it).

Highlight inconsistent variable values across nodes.

Determine which control branch should have been taken but wasn’t.

2. Produce a Minimal, Safe Fix

Your suggested fix must:

Modify as few lines as possible

Maintain original coding style

Avoid introducing new side effects

Preserve external interfaces and assumptions

3. Explain the Bug and Fix

Provide a clear breakdown:

What the bug is

Where it occurs (file + line or function + CFG node ID)

Why it breaks execution or test expectations

What the corrected behavior should be

The corrected code snippet

4. Provide Patch-style Output

Return code changes in this exact format:

=== PATCH START ===
<diff or edited code>
=== PATCH END ===

5. If Multiple Fixes Are Possible:

Suggest the safest fix first

Then list alternative improvements separately

Never mix alternatives inside the main fix

6. Use the CFG When Reasoning

You must leverage CFG details such as:

Incorrect branch transitions

Missing JOIN nodes

Unreachable blocks

Loops that never terminate or never execute

Misordered returns

Incorrect exception paths

Variables overwritten before use

Missing initialization or reinitialization

Dead control-flow edges

State inconsistencies: e.g.,

A variable set in Node 12 but not present in Node 13

A function returning early without updating required state

Your Output Structure

Always reply in this exact structure:

1. Root Cause Summary

One paragraph describing the precise underlying issue.

2. Evidence from CFG + Trace

Bullet list referencing:

Node IDs

Variable states

Branch outcomes

Relevant code locations

3. Corrected Behavior Description

Explain what should have happened.

4. Minimal Patch

Use === PATCH START === and === PATCH END ===.

5. Optional Improvements

Only after the patch.

Example Invocation Format (what the agent passes)

The agent will format input as:

<CFG_JSON>
<RUNTIME_TRACE>
<FAILING_TEST_LOGS>
<DIFFS>
<RELEVANT_CODE_SNIPPETS>
<ADDITIONAL_NOTES>

The model should strictly follow the output structure regardless of input.
    """


def get_sample_input():

    return """
<CFG_JSON>
{
  "modules": {
    "project/utils/math_ops.py": {
      "functions": {
        "compute_average": {
          "entry": "n1",
          "nodes": {
            "n1": { "id": "n1", "type": "ENTRY", "code": "", "edges": ["n2"] },
            "n2": { "id": "n2", "type": "IF", "code": "if len(values) == 0:", "edges": ["n3", "n4"] },
            "n3": { "id": "n3", "type": "RETURN", "code": "return 0", "edges": [] },
            "n4": { "id": "n4", "type": "ASSIGN", "code": "total = sum(values)", "edges": ["n5"] },
            "n5": { "id": "n5", "type": "RETURN", "code": "return total / len(values)", "edges": [] }
          },
          "cross_references": []
        }
      }
    },
    "project/services/analyzer.py": {
      "functions": {
        "analyze_numbers": {
          "entry": "a1",
          "nodes": {
            "a1": { "id": "a1", "type": "ENTRY", "code": "", "edges": ["a2"] },
            "a2": { "id": "a2", "type": "FOR", "code": "for i in range(len(nums)):", "edges": ["a3", "a6"] },
            "a3": { "id": "a3", "type": "ASSIGN", "code": "avg = compute_average(nums[:i])", "edges": ["a4"] },
            "a4": { "id": "a4", "type": "IF", "code": "if avg > threshold:", "edges": ["a5", "a2"] },
            "a5": { "id": "a5", "type": "RETURN", "code": "return i", "edges": [] },
            "a6": { "id": "a6", "type": "RETURN", "code": "return -1", "edges": [] }
          },
          "cross_references": [
            {
              "caller_node": "a3",
              "call_target": "compute_average"
            }
          ]
        }
      }
    }
  }
}
</CFG_JSON>

<RUNTIME_TRACE>
{
  "project/services/analyzer.py::analyze_numbers": {
    "a1": { "nums": [5, 7, 10], "threshold": 6 },
    "a2": { "i": 0 },
    "a3": { "i": 0, "avg_call_arg": [] },
    "a4": { "i": 0, "avg": 0 },
    "a2(loop)": { "i": 1 },
    "a3(loop)": { "i": 1, "avg_call_arg": [5] },
    "a4(loop)": { "i": 1, "avg": 5 },
    "a2(loop2)": { "i": -1 },  
    "error": "IndexError: range() step cannot be negative"
  }
}
</RUNTIME_TRACE>


<FAILING_TEST_LOGS>
=====================================
FAIL: test_analyze_numbers_threshold
-------------------------------------
Traceback (most recent call last):
  File "tests/test_analyzer.py", line 19, in test_analyze_numbers_threshold
    assert analyze_numbers([5,7,10], threshold=6) == 1
AssertionError: Expected 1 but got -1

Captured error during execution:
IndexError: range() step cannot be negative

Additional notes:
Loop index became negative (i = -1) unexpectedly.
=====================================
</FAILING_TEST_LOGS>


<DIFFS>
--- analyzer.py (before)
+++ analyzer.py (after)
@@
- for i in range(len(nums)):
+ for i in range(len(nums) - 1):

(The developer incorrectly tried to “optimize” by subtracting 1 from the loop range, causing i to go out of sync and later become negative.)

</DIFFS>

<RELEVANT_CODE_SNIPPETS>
# project/services/analyzer.py

def analyze_numbers(nums, threshold):
    for i in range(len(nums) - 1):   # BUG: should be range(len(nums))
        avg = compute_average(nums[:i])
        if avg > threshold:
            return i
    return -1

# project/utils/math_ops.py

def compute_average(values):
    if len(values) == 0:
        return 0
    total = sum(values)
    return total / len(values)
</RELEVANT_CODE_SNIPPETS>


<ADDITIONAL_NOTES>
- CFG node a2 shows the loop header.
- Runtime trace shows 'i' becomes -1 at one point, causing the index error.
- Downstream failure: returning -1 when the test expects index 1.
- This input is meant to trigger a full debugging analysis from the LLM.
</ADDITIONAL_NOTES>



"""


def get_cfg_parser():
    return """

For a given prompt, parse the code blocks in it into 

"""