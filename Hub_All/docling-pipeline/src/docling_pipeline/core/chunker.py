"""Wrapper Docling HybridChunker với tokenizer string overload + per-request override.

Trách nhiệm:
1. Build HybridChunker với tokenizer string ('cl100k_base' default — Docling 2.x resolve
   tiktoken nội bộ; tránh import tokenizer object manual để khỏi drift API).
2. Per-request override qua ChunkerOptions (CHUNK-01 + CHUNK-02).
3. KHÔNG augment Q&A/keyword (CHUNK-04 — giữ pristine, augmenter Go xử sau).

Tham chiếu:
- CONTEXT.md mục C (tokenizer chốt cl100k_base).
- CHUNK-01..04 trong REQUIREMENTS.md.
- Revision B2: dùng string overload thay vì import tokenizer object manual.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import structlog
from docling.chunking import HybridChunker
from docling_core.transforms.chunker import DocChunk
from docling_core.types.doc import DoclingDocument

from docling_pipeline.config import Settings, get_settings

logger = structlog.get_logger(__name__)

# Whitelist tokenizer name — chỉ accept tiktoken encodings Docling resolve được nội bộ.
# CONTEXT.md mục C: cl100k_base default cho OpenAI text-embedding-3-*; cũng dùng cho Gemini
# làm workaround sai số ±10%. HuggingFace tokenizer (Gemini native) defer M3.
_TIKTOKEN_NAMES = {"cl100k_base", "p50k_base", "p50k_edit", "r50k_base", "o200k_base"}


@dataclass(frozen=True)
class ChunkerOptions:
    """Per-request chunker overrides (CHUNK-02 — admin có thể truyền qua body)."""

    tokenizer_name: str | None = None
    max_tokens: int | None = None
    merge_peers: bool = True
    # repeat_table_header + omit_header_on_overflow là default Docling — không expose
    # cho client trừ khi cần tinh chỉnh; CONTEXT mục C giữ default.

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ChunkerOptions":
        if not data:
            return cls()
        return cls(
            tokenizer_name=data.get("tokenizer_name"),
            max_tokens=data.get("max_tokens"),
            merge_peers=bool(data.get("merge_peers", True)),
        )


def _validate_tokenizer_name(name: str) -> str:
    """Validate tokenizer name — chỉ accept tiktoken whitelist. Fail loud nếu unknown."""
    if name not in _TIKTOKEN_NAMES:
        raise ValueError(
            f"unsupported tokenizer_name {name!r} — currently support: {sorted(_TIKTOKEN_NAMES)}"
        )
    return name


class DoclingChunker:
    """Wrapper HybridChunker — single instance reuse cho default config.

    Per-request override sẽ build chunker mới on-demand (rare path).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._default_chunker = self._build_chunker(
            tokenizer_name=self.settings.tokenizer_name,
            max_tokens=self.settings.max_tokens_per_chunk,
            merge_peers=True,
        )

    def _build_chunker(
        self,
        tokenizer_name: str,
        max_tokens: int,
        merge_peers: bool,
    ) -> HybridChunker:
        # B2: string overload — Docling 2.x resolve tiktoken nội bộ.
        # KHÔNG import tokenizer object (Openai/Base) manual — path drift giữa các patch 2.91.x.
        validated = _validate_tokenizer_name(tokenizer_name)
        return HybridChunker(
            tokenizer=validated,
            max_tokens=max_tokens,
            merge_peers=merge_peers,
        )

    def chunk(
        self, doc: DoclingDocument, options: ChunkerOptions | None = None
    ) -> list[DocChunk]:
        """Chunk DoclingDocument → list DocChunk Docling raw (chưa serialize)."""
        options = options or ChunkerOptions()

        # Hot path: dùng default chunker khi options không override
        if (
            options.tokenizer_name is None
            and options.max_tokens is None
            and options.merge_peers is True
        ):
            chunker = self._default_chunker
            tok_name = self.settings.tokenizer_name
            mt = self.settings.max_tokens_per_chunk
        else:
            tok_name = options.tokenizer_name or self.settings.tokenizer_name
            mt = options.max_tokens or self.settings.max_tokens_per_chunk
            chunker = self._build_chunker(tok_name, mt, options.merge_peers)

        logger.info(
            "chunk_start",
            tokenizer=tok_name,
            max_tokens=mt,
            merge_peers=options.merge_peers,
        )
        chunks = list(chunker.chunk(dl_doc=doc))
        logger.info("chunk_done", chunks=len(chunks))
        return chunks


@lru_cache(maxsize=1)
def get_chunker() -> DoclingChunker:
    return DoclingChunker()


def chunk_document(
    doc: DoclingDocument, options: ChunkerOptions | None = None
) -> list[DocChunk]:
    """Convenience entry để API layer gọi (Plan 02-06)."""
    return get_chunker().chunk(doc, options)
