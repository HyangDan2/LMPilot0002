from __future__ import annotations

from .results import SlashToolResult


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

/workspace_status
Show which document-pipeline artifacts are available in the attached folder.

/generate_markdown
Generate a deterministic markdown report from extracted evidence.

/generate_report [--no-llm] [--max-chars N] [--llm-input-chars N] [query...]
Run extraction, mapping, chunking, output planning, context-safe LLM orchestration, and final Markdown report generation in one step.
No prerequisite slash command is required. It always rebuilds fresh artifacts from the attached folder.

Examples:
  /generate_report summarize all output in this folder
  /generate_report summarize about project risks
  /generate_report --no-llm summarize briefly

Supported file types:
.pptx, .docx, .xlsx, .pdf

Suggested flow:
1. Attach a folder.
2. Run /generate_report.
3. Run /workspace_status.

Advanced evidence flow:
1. Run /extract_docs.
2. Run /build_doc_map.
3. Run /chunk_sections.
4. Run /generate_markdown.

Automatic saved outputs:
- /extract_docs saves llm_result/document_pipeline/extracted_documents.json
- /extract_docs saves llm_result/document_pipeline/extraction_manifest.json
- /extract_single_doc saves llm_result/document_pipeline/documents/DOCUMENT_ID.json
- /build_doc_map saves llm_result/document_pipeline/document_map.json
- /chunk_sections saves llm_result/document_pipeline/chunks.json
- /generate_report saves llm_result/document_pipeline/output_plan.json
- /generate_report saves llm_result/document_pipeline/llm_chunk_summaries.json
- /generate_report saves llm_result/document_pipeline/llm_section_summaries.json
- /generate_report saves llm_result/document_pipeline/llm_report_attempts.json
- /generate_markdown saves llm_result/document_pipeline/generated_report.md
- /generate_report saves llm_result/document_pipeline/generated_report.md

Not included yet:
- summarize_map
- integrated_result
- streaming report generation
"""


def help_command(args, working_folder, context) -> SlashToolResult:
    return SlashToolResult(
        text=HELP_TEXT,
        tool_name="/help",
        next_actions=["/extract_docs", "/workspace_status"],
    )
