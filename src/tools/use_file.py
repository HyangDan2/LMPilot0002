from __future__ import annotations

from src.gemma_console_gui.attachment_handler import (
    AttachmentError,
    extract_text_from_file,
    format_attachment_context,
    format_user_text_with_attachments,
)

DEFAULT_USE_FILE_INSTRUCTION = "Please review the attached file(s)."


class UseFileError(Exception):
    pass


def build_use_file_prompt(paths: list[str], instruction: str = "") -> str:
    if not paths:
        raise UseFileError("Attach at least one file before using ./use_file.")

    attachments: list[dict[str, str]] = []
    failures: list[str] = []
    for path in paths:
        try:
            extracted = extract_text_from_file(path)
        except AttachmentError as exc:
            failures.append(str(exc))
            continue
        attachments.append(
            {
                "filename": extracted.filename,
                "path": extracted.path,
                "file_type": extracted.file_type,
                "extracted_text": extracted.extracted_text,
            }
        )

    if not attachments:
        detail = "; ".join(failures) if failures else "No usable attached files."
        raise UseFileError(detail)

    attachment_context = format_attachment_context(attachments)
    if failures:
        attachment_context = (
            f"{attachment_context}\n\n"
            "Attachment warnings:\n"
            + "\n".join(f"- {failure}" for failure in failures)
        )
    prompt_instruction = instruction.strip() or DEFAULT_USE_FILE_INSTRUCTION
    return format_user_text_with_attachments(prompt_instruction, attachment_context)
