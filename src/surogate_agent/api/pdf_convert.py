"""
Utility for converting Office documents (doc/docx) to PDF using LibreOffice headless.

LibreOffice must be installed in the runtime environment.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from surogate_agent.core.logging import get_logger

log = get_logger(__name__)

_CONVERTIBLE = frozenset([".doc", ".docx"])


def is_convertible(path: Path) -> bool:
    return path.suffix.lower() in _CONVERTIBLE


def convert_to_pdf(source: Path) -> Path:
    """Convert *source* (doc/docx) to PDF using LibreOffice headless.

    Returns the path to the converted PDF inside a temporary directory.
    The **caller is responsible** for deleting the parent directory
    (``returned_path.parent``) after the response has been sent.

    Raises ``RuntimeError`` if LibreOffice is not available or conversion fails.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="surogate_pdf_"))
    try:
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(tmp_dir),
                str(source),
            ],
            check=True,
            timeout=60,
            capture_output=True,
            text=True,
        )
        log.debug("libreoffice stdout: %s", result.stdout.strip())
        if result.stderr.strip():
            log.debug("libreoffice stderr: %s", result.stderr.strip())
        pdf_path = tmp_dir / (source.stem + ".pdf")
        if not pdf_path.is_file():
            # LibreOffice exits 0 even when it cannot load the source file;
            # stderr contains the real reason (e.g. "source file could not be loaded").
            detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise RuntimeError(
                f"Could not convert '{source.name}' to PDF: {detail}"
            )
        return pdf_path
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"PDF conversion failed for '{source.name}': {exc}") from exc
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
