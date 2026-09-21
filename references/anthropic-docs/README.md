# references/anthropic-docs/

This directory is populated by `scripts/refresh_docs.py` and is intentionally
left empty in version control until the manual refresh command is run:

```
python3 scripts/refresh_docs.py
```

Each generated `<doc-name>.md` file is prefixed with a `fetched_at: <ISO
date>` header line followed by the verbatim fetched content.
