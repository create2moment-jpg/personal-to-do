"""OCR through the local AI model, when it can read images (no extra installs).

Each scanned page image goes to the user's own model server (llama.cpp with a
vision model and --mmproj, Ollama, LM Studio, vLLM). The transcription is
labelled as model output so the user checks quotes against the original.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from ppos.ai.provider import AIUnavailableError, LLMResult
from ppos.domain.documents import ExtractedPage
from ppos.infrastructure.pdf_images import page_images
from ppos.shared.errors import PposError, ValidationError

# (system, prompt, images, max_tokens) -> result
VisionCall = Callable[[str, str, list[tuple[str, bytes]], int], LLMResult]

_FENCE = re.compile(r"^```[\w-]*\n(.*)\n```$", re.DOTALL)


def clean_transcript(text: str) -> str:
    t = re.sub(r"^<think>.*?</think>\s*", "", text.strip(), flags=re.DOTALL)
    m = _FENCE.match(t)
    return (m.group(1) if m else t).strip()


def vision_ocr(
    data: bytes, call: VisionCall, system: str, prompt: str, max_tokens: int = 2000
) -> list[ExtractedPage]:
    images = page_images(data)
    if not images:
        raise ValidationError("no scanned page images found in this PDF")
    pages: list[ExtractedPage] = []
    for img in images:
        try:
            r = call(system, prompt, [(img.mime, img.data)], max_tokens)
        except AIUnavailableError as exc:
            if "cannot reach" in str(exc) or "is off" in str(exc):
                raise
            raise ValidationError(_hint(img.page, exc)) from exc
        except PposError as exc:
            raise ValidationError(_hint(img.page, exc)) from exc
        pages.append(ExtractedPage(img.page, clean_transcript(r.text)))
    return pages


def _hint(page: int, exc: Exception) -> str:
    return (
        f"the local model could not read page {page} ({str(exc)[:160]}) — reading scans "
        "needs a model that understands images (llama.cpp: a vision model started with "
        "--mmproj), or Tesseract on this machine"
    )
