# Corporate Engineering Standard: Python Code Quality & Maintainability

**Policy ID:** QUAL-001  
**Category:** QUALITY  
**Version:** 1.0.0  
**Effective Date:** 2026-01-01  
**Target Languages:** Python  

## 1. Cyclomatic Complexity and Function Length
Functions must be focused and adhere to the Single Responsibility Principle.
- Cyclomatic complexity must not exceed 10 per function.
- Function length must not exceed 60 physical lines of code (excluding docstrings).
- Deep nesting beyond 3 indentation levels must be refactored into helper methods or guard clauses.

## 2. Exception Handling and Swallowing
Silent exception swallowing using bare `except:` or `except Exception: pass` is strictly prohibited.
- Always catch specific exception types (e.g. `ValueError`, `KeyError`, `httpx.HTTPError`).
- Log caught exceptions with structured diagnostic context or re-raise with `raise ... from err`.

## 3. Clean Code and Production Cleanliness
Debugging artifacts including raw `print()` statements, temporary mock dumps, and wildcard imports (`from module import *`) must be removed prior to merge.
- Use structured logging via the platform standard logger (`app.utils.logging.get_logger`).
- Explicitly import only required symbols and modules.
