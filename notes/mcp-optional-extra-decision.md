---
uuid: mf-mcp-optional-extra
title: "Packaging: why mcp is an optional extra, not a core dependency"
summary: "mcp pulls in 14 extra packages (cryptography, starlette, uvicorn, pydantic, and their trees) nothing in the core search/read/write path touches; moved to `mf[mcp]` after measuring the real install cost."
status: active
tags: [packaging, mcp, dependencies]
---
## Answer
`mf mcp` needs the `mcp` package, but core `mf` usage (the CLI itself,
or the Claude Code skill calling `search`/`read`/`write` directly)
never touches it. Measured the real cost before deciding: building
into a scratch `UV_TOOL_DIR` with and without `mcp` installed 30
packages without it, 44 with it -- 14 extra packages
(`cryptography`, `starlette`, `uvicorn`, `pydantic`, and their own
transitive trees) for a feature most installs won't use.

Moved `mcp` from a core dependency to the `mcp` optional extra
(matching the existing `eval`/`mlx` precedent in `pyproject.toml`),
duplicated into the `dev` dependency group so the test suite still
installs it. `mf mcp` without the extra now exits 1 with the install
command (`uv tool install '.[mcp]'` / `pip install 'memoryfield[mcp]'`) instead
of a raw `ImportError` traceback.

Install with:
```bash
uv tool install ".[mcp]"
```
