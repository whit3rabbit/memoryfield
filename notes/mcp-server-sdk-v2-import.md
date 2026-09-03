---
uuid: mf-mcp-sdk-v2-import
title: "mf mcp: why it imports MCPServer, not FastMCP"
summary: "mcp Python SDK v2 renamed FastMCP to MCPServer and moved the import path; `from mcp.server.fastmcp import FastMCP` is a dead stub in mcp>=2 that raises ModuleNotFoundError."
status: active
tags: [mcp, packaging, gotcha]
---
## Answer
`mf/mcp_server.py` imports `from mcp.server import MCPServer`, not the
widely-documented `from mcp.server.fastmcp import FastMCP`. The v1 API
(`FastMCP`) was renamed to `MCPServer` and moved in v2, so the old
import path is a stub in `mcp>=2` that raises `ModuleNotFoundError`
pointing at a migration guide, not a working import.

Confirmed the current API surface against Context7's SDK docs before
writing to it (this repo pins `mcp>=2.1,<3`; installed version was
2.1.1 when checked). Verify the installed SDK version before trusting
any mcp code sample, training-data or otherwise -- this is exactly the
kind of API that changes shape between major versions.
