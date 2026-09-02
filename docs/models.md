# Choosing an embedding model

[Docs](README.md) | [Agents](agents.md) | [CLI](CLI.md) | [Models](models.md) | [Fields](fields.md) | [Architecture](architecture.md) | [Benchmarks](BENCHMARKS.md)

The default is `snowflake-arctic-embed-xs`, and most fields should
keep it. Pick another model only for one of the reasons below, and
pick it at `mf init` time, because the model is pinned per field.

## The default and why

`snowflake-arctic-embed-xs` is a 384-dimension model, about 170 MB on
disk. On the blind phrasing sets it scored 0.950 average top-1, second
only to its larger sibling, while loading in 33 ms against 210 ms for
the 768-d nomic model the spec suggests. Its vectors take half the
space of a 768-d model. The full comparison, including the models that
won one axis and lost another, is [Benchmarks, section
1](BENCHMARKS.md#1-embedding-models-benchmark).

The first `mf search` on a machine downloads the model. `mf model
install` does that ahead of time.

## Available models

`mf model list` prints the registry with dimensions, download size,
query latency, and whether each model is already cached. The table is
in the [CLI reference](CLI.md#mf-model-list). The descriptions come
from `MODEL_REGISTRY` in `mf/embedder.py`, so the installed command is
the current list.

## When to pick which

- `snowflake-arctic-embed-xs` (default): the fastest query latency
  measured, 0.950 blind top-1, 384-d.
- `snowflake-arctic-embed-s`: the highest blind top-1 in the benchmark
  (0.975), at about twice the load time and 255 MB.
- `bge-small-en-v1.5`: the smallest download in the registry (130 MB),
  with blind accuracy equal to the default.
- `nomic-embed-text-v1.5`: the model the memoryfield spec suggests.
  Pick it when the field will be packed with `mf pack --spec` for a
  reader that expects a nomic index ([Architecture, section
  6](architecture.md#6-pack)). 768-d, 520 MB, slower to load.
- `bge-large-en-v1.5`: 1024-d and 2.5 GB. Equal to the default on
  blind top-1 here, so only worth it if a later blind set shows the
  small models losing.
- `jina-embeddings-v2-small-en`: an 8192-token context window. Only
  matters for pages far above the 800-token lint ceiling, which the
  writing conventions discourage.
- `all-MiniLM-L6-v2` and `bge-base-en-v1.5`: baselines kept for
  comparison, not recommendations.

Every number in those bullets is from [Benchmarks, section
1](BENCHMARKS.md#1-embedding-models-benchmark). The mxbai Matryoshka
rows in that table were measured but are not in the registry: they
need an ONNX export to avoid a multi-second PyTorch import on every
CLI call.

## Pinned per field

`mf init --model <name>` writes the model and its dimension into the
index's `config` table. Every later `mf index`, `mf search`, and `mf
write` reads them from there, so a field never mixes vectors from two
models.

There is no in-place migration. To change models, delete `mf.sqlite3`,
run `mf init --model <name>`, then `mf index`. The pages are untouched.
The `reads` log, `co_read` weights, and `claims` live only in the
index and are lost ([Architecture, section
2](architecture.md#2-index-derived-mostly-deletable)).

## Pre-download

```bash
mf model install snowflake-arctic-embed-xs
```

This downloads and warms the model so the first search on a fresh
machine does not pay for it. `mf model list` shows what is cached.

## MLX backend

Set `MF_EMBED_BACKEND=mlx` on Apple Silicon, with the `mlx` extra
installed, to embed through MLX instead of ONNX. It is opt-in and never
auto-selected. An index's vectors must all come from one runtime, and
the two runtimes differ slightly for the same checkpoint, so switching
silently would shift every distance the gate is calibrated on. MLX
covers `nomic-embed-text-v1.5` and `bge-large-en-v1.5` only.

## Calibration caveat

The confidence and dedup thresholds were calibrated on nomic
distances. The default model has been measured against them on one
blind field so far. Until the sweep is rerun on arctic-xs, treat
`confidence` on a default field as calibrated by analogy rather than
by measurement. [Architecture, "Known gaps"](architecture.md#known-gaps)
tracks it.
