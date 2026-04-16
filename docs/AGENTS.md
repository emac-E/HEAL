# AI Agent Guidelines for HEAL

This document provides guidelines for AI coding agents working on the HEAL project.

---

## ⚠️ CRITICAL RULES

### 1. **READ FIRST, DON'T GUESS**

When working with code you haven't seen:

❌ **WRONG - Guessing:**
```python
# Guessing the class name
from heal.core.linux_expert import LinuxExpert  # Wrong!
```

✅ **CORRECT - Reading first:**
```bash
# Check what's actually in the file
grep "^class " src/heal/core/linux_expert.py

# Result: class LinuxExpertAgent
from heal.core.linux_expert import LinuxExpertAgent  # Correct!
```

**Before writing code that imports/calls/extends a module:**
1. Read the file with `Read` tool or `grep` for class/function names
2. Check what's actually exported
3. Then write your code

### 2. **Use pytest-mock, NEVER unittest.mock**

❌ **WRONG:**
```python
from unittest.mock import patch, MagicMock
```

✅ **CORRECT:**
```python
def test_example(mocker):  # pytest-mock fixture
    mocker.patch('heal.agents.okp_mcp_agent.something')
```

### 3. **Run Quality Checks Before Completing Work**

Before considering any code change complete:

```bash
make format        # Format code
make lint          # Check linting
make type-check    # Type check
make test          # Run tests
```

**Do NOT skip these steps.** If checks fail:
1. Fix issues in code you changed
2. For pre-existing issues in unchanged code: notify user but don't fix
3. Re-run checks until they pass

### 4. **Update Documentation When Changing Features**

When modifying functionality:
- Update relevant docs in `docs/`
- Update `README.md` if user-facing features change
- Update this `AGENTS.md` if adding new conventions

---

## Project Structure

```
HEAL/
├── src/heal/              # Main package (src/ layout)
│   ├── agents/           # Agent implementations
│   ├── core/             # Core components
│   ├── bootstrap/        # JIRA extraction
│   ├── pattern_discovery/ # Pattern analysis
│   └── runners/          # Workflow runners
├── tests/                # Test suite (pytest)
├── config/               # Configuration files
├── docs/                 # Documentation
├── pyproject.toml        # Project config
└── Makefile              # Dev commands
```

---

## Code Standards

### Type Hints
Required for all public functions:
```python
def evaluate_ticket(ticket_id: str) -> EvaluationResult:
    """Evaluate a JIRA ticket."""
    ...
```

### Docstrings
Google-style for all public APIs:
```python
def diagnose(self, ticket_id: str) -> EvaluationResult:
    """Diagnose a JIRA ticket.
    
    Args:
        ticket_id: JIRA ticket ID (e.g., "RSPEED-123")
        
    Returns:
        Evaluation results with metrics and classification
        
    Raises:
        ValueError: If ticket_id is invalid
    """
```

### Error Handling
Use descriptive error messages:
```python
# Good
if not ticket_id.startswith("RSPEED-"):
    raise ValueError(f"Invalid ticket ID format: {ticket_id}")

# Bad
if not ticket_id.startswith("RSPEED-"):
    raise ValueError("Invalid ticket")
```

### Logging
Use structured logging:
```python
import logging

logger = logging.getLogger(__name__)
logger.info("Processing ticket %s", ticket_id)
```

---

## Testing Guidelines

### Test Structure
Mirror source structure:
```
src/heal/agents/okp_mcp_agent.py
tests/test_agents/test_okp_mcp_agent.py
```

### Naming Conventions
- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

### Mocking with pytest-mock
```python
def test_agent_with_mocked_api(mocker):
    """Test agent with mocked API calls."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    
    mocker.patch('heal.agents.okp_mcp_agent.requests.post', 
                 return_value=mock_response)
    
    agent = OkpMcpAgent(...)
    result = agent.diagnose("RSPEED-123")
    
    assert result.success
```

### Coverage Target
Aim for >80% on new code:
```bash
make test-cov
```

---

## Common Workflows

### Adding a New Agent

1. **Create the agent file:**
   ```bash
   touch src/heal/agents/my_new_agent.py
   ```

2. **Read existing agents first:**
   ```bash
   cat src/heal/agents/okp_mcp_agent.py
   # Understand the patterns before implementing
   ```

3. **Implement following existing patterns:**
   - Inherit from base classes if available
   - Use same logging/error handling patterns
   - Follow same initialization patterns

4. **Create tests:**
   ```bash
   touch tests/test_agents/test_my_new_agent.py
   ```

5. **Add import test:**
   ```python
   # In tests/test_imports.py
   def test_import_my_new_agent():
       """Test MyNewAgent import."""
       from heal.agents.my_new_agent import MyNewAgent
       assert MyNewAgent is not None
   ```

6. **Run checks:**
   ```bash
   make quality-checks
   make test
   ```

### Adding a New Dependency

1. **Add to pyproject.toml:**
   ```toml
   dependencies = [
       "new-package>=1.0.0",
       ...
   ]
   ```

2. **Update lockfile:**
   ```bash
   uv sync --extra dev
   ```

3. **Verify it works:**
   ```bash
   uv run python -c "import new_package; print('OK')"
   ```

---

## Troubleshooting

### Import Errors

**Problem:** `ImportError: cannot import name 'ClassName'`

**Solution:**
```bash
# Don't guess! Check what's actually in the file:
grep "^class " src/heal/path/to/file.py
grep "^def " src/heal/path/to/file.py

# Or read the file:
head -50 src/heal/path/to/file.py
```

### Test Failures

**Problem:** Tests fail after changes

**Solution:**
```bash
# Run specific test with verbose output
uv run pytest tests/test_specific.py -v -s

# Check what changed
git diff

# Read the test to understand what it expects
cat tests/test_specific.py
```

### Dependency Issues

**Problem:** `ModuleNotFoundError` after adding dependency

**Solution:**
```bash
# Ensure you synced after adding to pyproject.toml
uv sync --extra dev

# Verify dependency was installed
uv pip list | grep package-name
```

---

## Before Submitting Changes

Checklist:

- [ ] Read relevant source files (didn't guess)
- [ ] Code formatted: `make format`
- [ ] Linting passes: `make lint`
- [ ] Type checking passes: `make type-check`
- [ ] Tests pass: `make test`
- [ ] Added tests for new functionality
- [ ] Updated documentation
- [ ] Imports tested (if new modules)

---

## Key Principles

1. **Read before writing** - Don't guess class names, function signatures, etc.
2. **Test everything** - Import tests, unit tests, integration tests
3. **Quality first** - Run all checks before marking work complete
4. **Document changes** - Keep docs in sync with code
5. **Follow patterns** - Look at existing code for consistency

---

## Questions?

Check the code first, then ask! 🚀
