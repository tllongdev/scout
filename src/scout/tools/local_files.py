"""Read local documents mounted into the container.

This is how Scout collects from sources that are *not* on the internet: drop
files into ./sources on the host (mounted read-only at /app/sources) and the
agent can list and read them - PDFs, text, markdown, CSVs, etc.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import trafilatura

from ..llm import Tool
from ..models import Mission, RawDocument

_ROOT = Path(os.getenv("SCOUT_SOURCES_DIR", "/app/sources"))
_MAX_CHARS = 8000
_TEXT_SUFFIXES = {".txt", ".md", ".csv", ".json", ".log", ".html", ".htm", ".xml"}


def local_files_tool(mission: Mission) -> Tool:
    def _handle(args: dict[str, Any]) -> str:
        action = str(args.get("action", "list")).strip().lower()
        if action == "list":
            return _list()
        if action == "read":
            return _read(args.get("path", ""), mission)
        return "Error: 'action' must be 'list' or 'read'."

    return Tool(
        name="local_files",
        description=(
            "Access local documents the user provided (offline sources not on "
            "the web). action='list' shows available files; action='read' with "
            "a 'path' returns a file's text. Use this for private dossiers, "
            "exports, or any material the user dropped into the sources folder."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "read"],
                    "description": "List available files or read one.",
                },
                "path": {
                    "type": "string",
                    "description": "Relative path of the file to read (for action='read').",
                },
            },
            "required": ["action"],
        },
        handler=_handle,
    )


def _list() -> str:
    if not _ROOT.exists():
        return "No local sources directory is mounted."
    files = [p for p in _ROOT.rglob("*") if p.is_file() and not p.name.startswith(".")]
    if not files:
        return "The local sources directory is empty."
    return "\n".join(str(p.relative_to(_ROOT)) for p in sorted(files))


def _read(rel_path: str, mission: Mission) -> str:
    rel_path = str(rel_path).strip()
    if not rel_path:
        return "Error: 'path' is required for action='read'."

    target = (_ROOT / rel_path).resolve()
    try:
        target.relative_to(_ROOT.resolve())
    except ValueError:
        return "Error: path escapes the sources directory."
    if not target.is_file():
        return f"Error: no such file '{rel_path}'."

    suffix = target.suffix.lower()
    try:
        if suffix == ".pdf":
            text = _read_pdf(target)
        elif suffix in _TEXT_SUFFIXES:
            text = target.read_text(errors="replace")
        else:
            return f"Unsupported file type '{suffix}'. Supported: PDF and text formats."
    except Exception as exc:  # noqa: BLE001
        return f"Failed to read {rel_path}: {exc}"

    mission.raw_documents.append(
        RawDocument(url=f"file://{rel_path}", title=target.name, content=text)
    )
    body = text[:_MAX_CHARS]
    truncated = " [...truncated]" if len(text) > _MAX_CHARS else ""
    return f"FILE: {rel_path}\n\n{body}{truncated}"


def _read_pdf(path: Path) -> str:
    downloaded = trafilatura.extract(path.read_bytes())  # type: ignore[arg-type]
    if downloaded:
        return downloaded
    # trafilatura doesn't do PDFs; fall back to a clear message.
    raise RuntimeError(
        "PDF text extraction is not available in this build. Convert to .txt "
        "or .md and place it in the sources folder."
    )
