# Benchmarks & Evaluation

All retrieval, ranking, schema, and model decisions in `mf` are backed by empirical measurements over real datasets and agent tasks.

---

## 1. Embedding Models Benchmark

A comprehensive evaluation comparing the baseline embedder (`nomic-embed-text-v1.5`, 768-d) against ultra-lightweight and alternative embedding models (`BGE-small-en-v1.5`, `snowflake-arctic-embed-xs/s`, `all-MiniLM-L6-v2`, `jina-v2-small-en`, and `mxbai-embed-xsmall-v1` with Matryoshka Representation Learning).

### Evaluation Setup & Methodology

- **Corpora**:
  - `codebase`: 75 pages, engineering documentation, operational runbooks, architecture decisions.
  - `papers`: 82 pages, ML research summaries, mathematical formulations, specialized terminology.
- **Query Sets**:
  - **In-Vocabulary Sets**: 174 queries on `codebase`, 254 queries on `papers` (428 total).
  - **Blind Phrasing Sets**: 20 queries on `codebase`, 20 queries on `papers` (40 total) authored independently without seeing the corpus text to evaluate realistic vocabulary mismatch.
- **Hardware & Runtime**: Apple Silicon (M-series), FastEmbed (ONNX Runtime CPU) and SentenceTransformers (PyTorch).

---

### Accuracy & Retrieval Quality Comparison

| Model | Dim | In-Vocab Top-1 (Avg) | Codebase In-Vocab | Papers In-Vocab | Blind Top-1 (Avg) | Codebase Blind Top-1 | Papers Blind Top-1 | Codebase Blind MRR | Papers Blind MRR |
|---|---|---|---|---|---|---|---|---|---|
| **BGE-small-en-v1.5** | **384** | **0.919** | 0.937 | 0.902 | **0.950** | **0.950** | **0.950** | **0.950** | **0.975** |
| **arctic-embed-xs** | **384** | **0.921** | 0.908 | 0.933 | **0.950** | **1.000** | **0.900** | **1.000** | **0.950** |
| **arctic-embed-s** | **384** | **0.905** | 0.897 | 0.913 | **0.975** | **1.000** | **0.950** | **1.000** | **0.975** |
| **nomic-embed-text-v1.5** *(Default)* | 768 | **0.923** | 0.925 | 0.921 | **0.925** | **0.950** | **0.900** | **0.975** | **0.925** |
| **nomic-embed-text-v1.5-Q** *(Quantized)* | 768 | **0.913** | 0.925 | 0.902 | **0.925** | **1.000** | **0.850** | **1.000** | **0.900** |
| **bge-large-en-v1.5** | 1024 | **0.934** | 0.954 | 0.913 | **0.950** | **0.950** | **0.950** | **0.967** | **0.975** |
| **bge-base-en-v1.5** | 768 | **0.927** | 0.937 | 0.917 | **0.925** | **0.950** | **0.900** | **0.975** | **0.950** |
| **all-MiniLM-L6-v2** | 384 | **0.878** | 0.885 | 0.870 | **0.925** | **1.000** | **0.850** | **1.000** | **0.910** |
| **jina-v2-small-en** | 512 | **0.911** | 0.908 | 0.913 | **0.925** | **0.950** | **0.900** | **0.960** | **0.935** |
| **mxbai-embed-xsmall (384d)** | 384 | **0.884** | 0.891 | 0.878 | **0.900** | **1.000** | **0.800** | **1.000** | **0.885** |
| **mxbai-embed-xsmall (256d MRL)** | 256 | **0.872** | 0.874 | 0.870 | **0.950** | **0.950** | **0.950** | **0.975** | **0.960** |
| **mxbai-embed-xsmall (192d MRL)** | 192 | **0.846** | 0.845 | 0.846 | **0.925** | **0.950** | **0.900** | **0.967** | **0.925** |
| **mxbai-embed-xsmall (128d MRL)** | 128 | **0.854** | 0.862 | 0.846 | **0.850** | **0.950** | **0.750** | **0.950** | **0.850** |

---

### Latency & On-Disk Footprint Comparison

| Model | Dim | Cached Load Time | Single Query Latency | Batch 75-Doc Indexing | Model Size (Disk) | Vector DB Size (10k docs, FP32) |
|---|---|---|---|---|---|---|
| **bge-small-en-v1.5** | 384 | **37.5 ms** | **2.4 ms** | **309 ms** | **128 MB** | **15.4 MB** |
| **arctic-embed-xs** | 384 | **33.0 ms** | **0.9 ms** | **94 ms** | **174 MB** | **15.4 MB** |
| **arctic-embed-s** | 384 | **57.9 ms** | **1.8 ms** | **198 ms** | **255 MB** | **15.4 MB** |
| **all-MiniLM-L6-v2** | 384 | **35.9 ms** | **3.1 ms** | **202 ms** | **174 MB** | **15.4 MB** |
| **jina-v2-small-en** | 512 | **42.4 ms** | **0.9 ms** | **140 ms** | **249 MB** | **20.5 MB** |
| **nomic-embed-text-v1.5** | 768 | **209.6 ms** | **4.6 ms** | **602 ms** | **520 MB** *(1.3 GB cache)* | **30.7 MB** |
| **nomic-embed-text-v1.5-Q** | 768 | **147.3 ms** | **3.2 ms** | **660 ms** | **130 MB** | **30.7 MB** |
| **bge-large-en-v1.5** | 1024 | **422.6 ms** | **12.6 ms** | **1,782 ms** | **2.55 GB** | **41.0 MB** |
| **mxbai-embed-xsmall (384d)** | 384 | ~2,860 ms *(PyTorch)* | **3.9 ms** | **229 ms** | **94 MB** | **15.4 MB** |
| **mxbai-embed-xsmall (256d)** | 256 | ~2,780 ms *(PyTorch)* | **4.8 ms** | **50 ms** | **94 MB** | **10.2 MB** |
| **mxbai-embed-xsmall (192d)** | 192 | ~2,797 ms *(PyTorch)* | **4.9 ms** | **40 ms** | **94 MB** | **7.7 MB** |
| **mxbai-embed-xsmall (128d)** | 128 | ~2,602 ms *(PyTorch)* | **4.7 ms** | **50 ms** | **94 MB** | **5.1 MB** |

---

### Key Takeaways

1. **`BGE-small-en-v1.5` offers the strongest overall efficiency**:
   - Accuracy matches or exceeds `nomic-v1.5` and `bge-large` on blind vocabulary tests (0.950 vs 0.925).
   - Cold-start load time drops **5.6x** (37.5 ms vs 209.6 ms).
   - Vector table footprint in SQLite is **cut by 50%** (384 vs 768 dimensions).
2. **`Snowflake Arctic-embed-xs / s` deliver exceptional speed and accuracy**:
   - `arctic-embed-xs` achieved 0.950 blind top-1 with sub-millisecond query latency (0.9 ms).
   - `arctic-embed-s` achieved the highest blind retrieval accuracy tested (0.975 top-1).
3. **Matryoshka Truncation (MRL) with `mxbai-embed-xsmall-v1`**:
   - 256-d truncation preserves strong retrieval accuracy (0.950 blind Top-1) while saving 33% vector storage.
   - Truncation to 128-d degrades recall on academic/technical queries (0.750 on papers blind).
   - Requires ONNX export to avoid the ~2.8s PyTorch import penalty during CLI invocations.
4. **`all-MiniLM-L6-v2` shows accuracy trade-offs**:
   - Fast and compact, but exhibited lower in-vocabulary accuracy (0.878) and struggled on nuanced semantic queries (0.850 on papers blind).

---

## 2. Ranking Architecture Benchmarks

Measured on the real `mf search` pipeline across blind phrasing sets:

| Ranking Strategy | Codebase Blind Top-1 | Papers Blind Top-1 | Avg Blind Top-1 |
|---|---|---|---|
| FTS-First | 0.700 | 0.800 | 0.750 |
| Symmetric RRF ($k=60$) | 0.800 | 0.850 | 0.825 |
| **Dense-First (Cosine)** | **0.950** | **0.900** | **0.925** |

RRF degrades performance by averaging FTS keyword noise into dense's semantic rankings.

---

## 3. Confidence Gate Benchmarks

Measured across 30 original no-answer queries, 48 blind no-answer queries, and a 10-page corpus subsample:

| Metric | v1.4 Gate (BM25 only) | v2.7 Gate (Dense Floor + BM25 + Agreement) |
|---|---|---|
| Usable Answers (Codebase Blind) | 0.550 | **0.900** |
| Usable Answers (Papers Blind) | 0.550 | **0.850** |
| Usable Answers (10-Page Subsample) | 0.185 | **0.889** |
| False-High on No-Answer Queries | 0/17 | **1/24** |

---

## 4. Token Cost Benchmarks

Measured across 20 real agent tasks (`eval/results/token_costs_2_11.txt`):

| Configuration | Token Cost per Lookup | Target Answer on Screen |
|---|---|---|
| Original (5 stubs / 3 neighbors) | 1,009 tokens (5.8x raw read) | 100% (20/20) |
| Lean Default (2 stubs / 0 neighbors) | **104 tokens (0.6x raw read)** | **100% (20/20)** |
| Point Lookup (1 stub / 0 neighbors) | **55 tokens** | **100% (20/20)** |
