# Database Naming Conventions (Milestone 3.1.2)

The following rules are enforced (currently for tables only):

1. snake_case: lowercase letters, digits, underscores. Must start with a letter.
2. Singular nouns: heuristic disallows names ending in 's' unless in an allowlist.
3. Internal / system tables (`sqlite_sequence`, `schema_meta`) are ignored.

Rationale:

- Consistency simplifies query writing and code generation.
- Singular table names map naturally to a row-as-entity mental model.
- snake_case aligns with Python naming style and most SQL style guides.

Planned future extensions:

- Column rules (snake_case, foreign key suffix `_id`).
- Index naming: `idx_<table>_<col1>[_<colN>]`.
- Foreign key constraint naming (if using explicit names in future migrations).

Validation Command:

```bash
python -m scripts.check_db_naming
```

Programmatic Use:

```python
import sqlite3
from db import apply_schema
from db.naming import validate_naming_conventions

conn = sqlite3.connect(":memory:")
apply_schema(conn)
violations = validate_naming_conventions(conn)
assert not violations
```
