# agent-config schema, vendored

`agent-config-agents.json` is `schema/agents.json` from
[whit3rabbit/agent-config](https://github.com/whit3rabbit/agent-config)
(crate version 0.4.0, upstream path audit 2026-06-21), copied
verbatim on 4 September 2026. It records where each coding-agent
harness keeps its project-local and global config for hooks, MCP,
skills, and instructions.

`mf/harnesses.py` hand-writes the ten harnesses `mf setup` supports
and `tests/test_harnesses.py` checks every path in it against this
file, so drift from upstream fails a test instead of writing to the
wrong place. Refresh by copying the file again and bumping the version
and date above.
