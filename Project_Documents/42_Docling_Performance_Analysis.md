# 42 — Docling Performance Analysis and Optimisation

**Project:** Flight Test Interactive Analysis Suite (FTIAS)
**Date:** 2026-04-04
**Status:** Optimisations Applied — Awaiting Benchmark Validation

---

## 1. Background

During Session 5, Docling was observed to be extremely slow when processing aviation PDF documents in the Docker container. One document remained in "Processing" status for an extended period. This document analyses the root causes and the optimisations applied.

---

## 2. Root Cause Analysis

### 2.1 Default Configuration Used

The original implementation called `DocumentConverter()` with no arguments, which activates the following defaults:

| Pipeline Step | Default | Cost |
|---|---|---|
| OCR (`do_ocr`) | **True** | Very High — runs a full neural OCR model on every page image |
| Table structure (`do_table_structure`) | True | Medium — runs TableTransformer model |
| Picture classification | False | — |
| Picture description | False | — |
| Page image generation | False | — |
| Picture image generation | False | — |
| Accelerator | AUTO (single thread) | High — no parallelism |

### 2.2 The OCR Bottleneck

OCR is the dominant bottleneck. Docling's default OCR pipeline:

1. Renders every PDF page to a raster image at the configured `images_scale`
2. Runs EasyOCR (a neural network) on each page image to extract text
3. Merges OCR output with the native PDF text layer

For **native-text PDFs** (which all aviation standards are — FAR, CS-25, RTCA DO-xxx, EASA AMC, etc.), this is entirely unnecessary. The text is already embedded in the PDF file. Running OCR on top of it doubles or triples processing time with no accuracy benefit.

**Estimated impact of disabling OCR: 60–75% reduction in processing time.**

### 2.3 The HybridChunker Tokenizer Download

The original code used:
```python
chunker = HybridChunker(tokenizer="BAAI/bge-small-en-v1.5", max_tokens=512)
```

This causes Docling to download the `BAAI/bge-small-en-v1.5` model from Hugging Face at runtime on the first call. Inside a Docker container without a persistent model cache, this download happens on every container restart, adding 1–3 minutes of latency before the first document can be processed.

### 2.4 Single-Threaded CPU Execution

The default `AcceleratorOptions` uses a single thread. The Docker container has access to multiple CPU cores. Explicitly setting `num_threads=4` allows Docling's layout analysis and table structure models to parallelise their work.

---

## 3. Optimisations Applied

The following changes were made to `backend/app/routers/documents.py` in the `parse_and_chunk_pdf` function:

### 3.1 Disable OCR

```python
pipeline_options.do_ocr = False
```

**Rationale:** All aviation standards (FAR, CS-25, RTCA DO-xxx, EASA AMC, MIL-SPEC, ANAC RBAC) are published as native-text PDFs. OCR is only needed for scanned documents (e.g., old paper manuals digitised as image-only PDFs).

**If you need to ingest a scanned document:** temporarily set `do_ocr = True` for that upload, or add a UI toggle in the Document Library "Add Document" form.

### 3.2 Keep Table Structure Extraction

```python
pipeline_options.do_table_structure = True
pipeline_options.table_structure_options = TableStructureOptions(do_cell_matching=True)
```

**Rationale:** Aviation standards contain critical performance tables (stall speeds, climb gradients, structural limits). Docling's TableTransformer accurately reconstructs these as structured data, which is then preserved as a single chunk in the RAG pipeline. This is the key accuracy advantage over simpler parsers like pymupdf4llm.

### 3.3 Disable All Enrichments and Image Generation

```python
pipeline_options.do_picture_classification = False
pipeline_options.do_picture_description = False
pipeline_options.do_code_enrichment = False
pipeline_options.do_formula_enrichment = False
pipeline_options.generate_page_images = False
pipeline_options.generate_picture_images = False
pipeline_options.generate_parsed_pages = False
```

**Rationale:** None of these outputs are used by the RAG pipeline. They add processing time and memory usage with no benefit for text-based Q&A.

### 3.4 Explicit CPU Parallelism

```python
pipeline_options.accelerator_options = AcceleratorOptions(
    num_threads=4,
    device=AcceleratorDevice.CPU,
)
```

**Rationale:** Docling's layout and table models can process multiple page regions in parallel. Setting `num_threads=4` is a safe default for a Docker container with 4+ vCPUs.

### 3.5 Replace BAAI Tokenizer with tiktoken

```python
chunker = HybridChunker(tokenizer="cl100k_base", max_tokens=512)
```

**Rationale:** `cl100k_base` is OpenAI's tiktoken tokenizer (already installed as a dependency of the `openai` package). It requires no model download and tokenises at native speed. The chunking quality is equivalent for English aviation text.

---

## 4. Expected Performance After Optimisation

Based on Docling benchmarks and community reports for similar workloads on CPU-only machines:

| Document Type | Before (estimated) | After (estimated) | Improvement |
|---|---|---|---|
| 10-page standard excerpt | 3–5 min | 20–40 sec | ~6–8× faster |
| 50-page chapter | 15–25 min | 2–4 min | ~6–8× faster |
| 200-page full document | 60–90 min | 8–15 min | ~6–8× faster |

*Note: First-call latency includes Docling model loading (~15–30 sec). Subsequent calls in the same container session are faster.*

---

## 5. When to Enable OCR

Set `do_ocr = True` only for these document types:

- Scanned paper manuals (image-only PDFs with no text layer)
- Old military specifications digitised before ~2000
- Documents where `pdftotext` or Adobe Acrobat extract only garbled text

**How to detect:** Open the PDF in a browser and try to select/copy text. If you can select text normally, OCR is not needed.

---

## 6. Future Optimisation Options (Not Yet Implemented)

### 6.1 Background Task Queue

Currently, PDF processing blocks the HTTP request until complete. For large documents, this causes the upload to appear frozen. **Recommended next step:** implement FastAPI `BackgroundTasks` so the upload endpoint returns immediately with status "Processing" and the indexing runs asynchronously.

### 6.2 Model Pre-warming

Docling loads its layout and table models on the first conversion call. Pre-warming at startup eliminates the first-call latency:

```python
# In main.py startup event
@app.on_event("startup")
async def prewarm_docling():
    from docling.document_converter import DocumentConverter
    # Instantiate converter once to load models into memory
    _converter_singleton = DocumentConverter()
```

### 6.3 GPU Acceleration

If the host machine has an NVIDIA GPU, switching to `device=AcceleratorDevice.CUDA` can provide an additional 3–5× speedup for the table structure model. Requires rebuilding the Docker image with a CUDA-enabled PyTorch build.

### 6.4 Scanned Document Support via RapidOCR

For scanned documents, replace EasyOCR with RapidOCR (already installed in the container):
```python
from docling.models.rapid_ocr_model import RapidOcrOptions
pipeline_options.do_ocr = True
pipeline_options.ocr_options = RapidOcrOptions()
```
RapidOCR is 3–5× faster than EasyOCR with comparable accuracy.

---

## 7. Decision: Keep Docling vs. Replace

**Recommendation: Keep Docling with the optimisations above.**

| Criterion | Docling (optimised) | pymupdf4llm | llamaparse |
|---|---|---|---|
| Table extraction accuracy | Excellent (TableTransformer) | Good (heuristic) | Excellent (cloud API) |
| Section/heading preservation | Excellent (HybridChunker) | Good | Good |
| Processing speed (text PDF) | Good after OCR disabled | Very Fast | Fast (API latency) |
| Offline/on-premise | Yes | Yes | No (cloud API) |
| Cost | Free | Free | Paid per page |
| Scanned document support | Yes (with OCR) | Limited | Yes |
| Aviation table fidelity | Best in class | Acceptable | Good |

Docling's structural accuracy for aviation documents — particularly its ability to reconstruct multi-column performance tables as structured data — justifies keeping it as the primary parser. The optimisations applied in this session address the performance gap without sacrificing accuracy.

pymupdf4llm remains a viable fallback option if processing time is still unacceptable after these optimisations are validated.
