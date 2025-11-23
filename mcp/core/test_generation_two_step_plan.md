# Two-Step Test Generation Plan

## Problem
The current single-step approach is failing validation because the LLM struggles to generate both test code AND structured metadata simultaneously. The `expected_output` field is coming back as null instead of a string.

## Solution: Two-Step Approach

### Step 1: Generate Test Code (Unstructured)
**Purpose**: Focus the LLM on writing good test code without worrying about structured output.

**Input**:
- Code snippet to test
- Optional context

**Output**: 
- Raw Python test code (multiple test cases)
- No structured output required - just code generation

**Prompt Focus**:
- Generate standalone, executable test code
- Mock all external dependencies
- Create multiple granular tests
- Each test should be self-contained

**LLM Call**: Simple text generation, no Pydantic model

### Step 2: Extract Structured Metadata (Structured)
**Purpose**: Analyze the generated test code and extract structured information.

**Input**:
- Generated test code from Step 1
- Original code snippet being tested
- Target function name (if known)

**Output**: 
- `GeneratedTestSuite` Pydantic model
- Extract: name, description, input, expected_output, notes for each test

**Prompt Focus**:
- Analyze the test code to identify:
  - Test names (from function names or comments)
  - Descriptions (what each test covers)
  - Input code (the test setup and function call)
  - Expected output/assertions (what the test asserts)
  - Notes (any special setup/teardown)

**LLM Call**: Structured output with `GeneratedTestSuite` model

## Implementation Details

### New Functions Needed

1. `generate_test_code_only()` - Step 1
   - Takes: code_snippet, context
   - Returns: str (raw Python test code)
   - Uses: Simple agent.run_sync() with text output

2. `extract_test_metadata()` - Step 2
   - Takes: generated_test_code, original_code_snippet, target_function (optional)
   - Returns: GeneratedTestSuite
   - Uses: agent.run_sync() with output_type=GeneratedTestSuite

3. `generate_tests_for_code()` - Updated wrapper
   - Calls Step 1, then Step 2
   - Returns GeneratedTestSuite

### Prompt Changes

**Step 1 Prompt** (`build_test_code_prompt`):
- Focus on code generation only
- No structured output requirements
- Emphasize standalone, executable tests
- Request multiple test cases as separate functions or test methods

**Step 2 Prompt** (`build_metadata_extraction_prompt`):
- Focus on analysis and extraction
- Clear structured output requirements
- Explicit instructions for each field:
  - `expected_output`: Extract assertions or expected results from test code
  - `input`: Extract the test setup and function call
  - `name`: Extract from function name or infer from test logic
  - `description`: Summarize what the test verifies

## Benefits

1. **Reliability**: Separates concerns - code generation vs. metadata extraction
2. **Validation**: Step 2 can validate that Step 1 produced valid test code
3. **Flexibility**: Can retry Step 2 if metadata extraction fails without regenerating code
4. **Clarity**: Each step has a single, clear objective

## Questions to Consider

1. **Error Handling**: What if Step 1 generates invalid code? Should we validate it before Step 2?
2. **Retries**: Should we retry Step 1 if code is invalid, or Step 2 if metadata extraction fails?
3. **Code Format**: Should Step 1 output be formatted in a specific way to make Step 2 easier?
   - Option A: Multiple test functions (one per test case)
   - Option B: Single test class with multiple methods
   - Option C: Plain code blocks with clear separators
4. **Target Function**: How do we identify the target function for Step 2?
   - Extract from Step 1 output?
   - Pass as parameter?
   - Infer from original code snippet?

## Proposed Code Structure

```python
def build_test_code_prompt(code_snippet: str, context: Optional[str] = None) -> str:
    """Generate raw test code only"""
    ...

def generate_test_code_only(
    *,
    agent: Agent,
    code_snippet: str,
    context: Optional[str] = None,
) -> str:
    """Step 1: Generate test code"""
    prompt = build_test_code_prompt(code_snippet, context)
    run_result = agent.run_sync(prompt)  # No output_type - just text
    return run_result.output

def build_metadata_extraction_prompt(
    generated_test_code: str,
    original_code_snippet: str,
    target_function: Optional[str] = None,
) -> str:
    """Extract structured metadata from test code"""
    ...

def extract_test_metadata(
    *,
    agent: Agent,
    generated_test_code: str,
    original_code_snippet: str,
    target_function: Optional[str] = None,
) -> GeneratedTestSuite:
    """Step 2: Extract structured metadata"""
    prompt = build_metadata_extraction_prompt(
        generated_test_code, original_code_snippet, target_function
    )
    run_result = agent.run_sync(prompt, output_type=GeneratedTestSuite)
    return run_result.output

def generate_tests_for_code(
    *,
    agent: Agent,
    code_snippet: str,
    context: Optional[str] = None,
) -> GeneratedTestSuite:
    """Main entry point - calls both steps"""
    # Step 1: Generate test code
    test_code = generate_test_code_only(
        agent=agent, code_snippet=code_snippet, context=context
    )
    
    # Step 2: Extract metadata
    suite = extract_test_metadata(
        agent=agent,
        generated_test_code=test_code,
        original_code_snippet=code_snippet,
    )
    
    return suite
```

