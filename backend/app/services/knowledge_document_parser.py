"""Small, format-aware parser for knowledge-base source documents.

This deliberately returns plain source text.  Chunking, embeddings and vector
indexing remain the responsibility of the existing RAG services.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile
from xml.etree import ElementTree


@dataclass(frozen=True)
class ParsedKnowledgeDocument:
    text: str
    parser: str
    pages: int | None = None


class KnowledgeDocumentParser:
    """Extract readable text from the formats accepted by FileStorageService."""

    async def parse(self, filename: str, content: bytes) -> ParsedKnowledgeDocument:
        suffix = Path(filename).suffix.lower()
        if suffix in {".txt", ".md"}:
            return ParsedKnowledgeDocument(content.decode("utf-8-sig", errors="replace").strip(), "plain_text")
        if suffix == ".docx":
            return ParsedKnowledgeDocument(self._docx_text(content), "docx_xml")
        if suffix == ".pdf":
            return self._pdf_text(content)
        raise ValueError("Unsupported knowledge document format")

    @staticmethod
    def _docx_text(content: bytes) -> str:
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        with ZipFile(BytesIO(content)) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        blocks: list[str] = []
        for paragraph in root.findall(".//w:p", namespace):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace)).strip()
            if text:
                blocks.append(text)
        return "\n".join(blocks)

    @staticmethod
    def _pdf_text(content: bytes) -> ParsedKnowledgeDocument:
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(content))
            text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
            if text:
                return ParsedKnowledgeDocument(text, "pypdf", len(reader.pages))
        except Exception:
            pass
        # Docling provides an OCR-capable fallback when it is configured in the
        # deployment.  Keeping it optional means basic TXT/DOCX/PDF workflows
        # never depend on a heavyweight model installation.
        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            # Docling 2.x receives an input path here.  A temporary file keeps
            # the parser compatible with the existing byte-oriented upload
            # service without persisting an extra user-owned copy.
            with NamedTemporaryFile(suffix=".pdf") as source:
                source.write(content)
                source.flush()
                result = converter.convert(source.name)
                text = result.document.export_to_markdown().strip()
            if text:
                return ParsedKnowledgeDocument(text, "docling", None)
        except Exception:
            pass
        return ParsedKnowledgeDocument("", "unreadable_pdf", None)
