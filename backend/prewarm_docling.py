"""
prewarm_docling.py
------------------
Pre-warms the Docling model cache inside the Docker container so that the
first PDF upload does not incur a model download delay.

Run once after starting the container:
    docker exec ftias-backend python /app/prewarm_docling.py

Models downloaded (~80 MB total):
  - sentence-transformers/all-MiniLM-L6-v2  (HybridChunker default tokenizer)
  - Docling layout and table structure models are loaded lazily on first convert()
    call and are already bundled with the docling package.
"""

import sys

print("Pre-warming Docling HybridChunker tokenizer...")
try:
    from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
    # Instantiating HybridChunker triggers the tokenizer download if not cached
    chunker = HybridChunker(max_tokens=512)
    print("  ✓ HybridChunker tokenizer ready (sentence-transformers/all-MiniLM-L6-v2)")
except Exception as e:
    print(f"  ✗ HybridChunker pre-warm failed: {e}")
    sys.exit(1)

print("\nPre-warming Docling DocumentConverter (layout models)...")
try:
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True
    pipeline_options.do_picture_classification = False
    pipeline_options.do_picture_description = False
    pipeline_options.generate_page_images = False
    pipeline_options.generate_picture_images = False
    pipeline_options.accelerator_options = AcceleratorOptions(
        num_threads=4, device=AcceleratorDevice.CPU
    )

    # Instantiating the converter loads the layout and table models into memory
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    print("  ✓ DocumentConverter models loaded")
except Exception as e:
    print(f"  ✗ DocumentConverter pre-warm failed: {e}")
    sys.exit(1)

print("\nDocling pre-warm complete. First PDF upload will be fast.")
