from __future__ import annotations


HELP_TEXT = """LLM Workspace Help

Local slash tools:

/help
Show this help text.

/detect_file_type PATH
Detect extension, MIME type, document family, and confidence for a file inside the attached folder.

/read_file_info PATH
Show file size and SHA-256 hash for a file inside the attached folder.

/normalize_text TEXT
Normalize whitespace, Unicode compatibility characters, and control characters.

/extract_single_doc PATH
Extract one supported document from the attached folder.

/extract_docs
Extract all supported documents from the attached folder.

/build_doc_map
Build a structural document map from the latest /extract_docs result. If needed, it loads saved extracted_documents.json.

/chunk_sections [--max-chars N]
Build retrieval chunks from the latest /extract_docs result. If needed, it loads saved extracted_documents.json.

Supported file types:
.pptx, .docx, .xlsx, .pdf

Suggested flow:
1. Attach a folder.
2. Run /extract_docs.
3. Run /build_doc_map.
4. Run /chunk_sections.

Automatic saved outputs:
- /extract_docs saves llm_result/document_pipeline/extracted_documents.json
- /extract_docs saves llm_result/document_pipeline/extraction_manifest.json
- /extract_single_doc saves llm_result/document_pipeline/documents/DOCUMENT_ID.json
- /build_doc_map saves llm_result/document_pipeline/document_map.json
- /chunk_sections saves llm_result/document_pipeline/chunks.json

Not included yet:
- summarize_map
- integrated_result
- report generation
- automatic LLM orchestration
"""


def help_command(args, working_folder, context) -> str:
    if args:
        return HELP_TEXT
    return HELP_TEXT
