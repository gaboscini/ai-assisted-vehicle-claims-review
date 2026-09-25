import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DocumentChunk:
    chunk_id: str
    source: str
    text: str


def chunk_markdown_file(file_path: Path) -> list[DocumentChunk]:
    document_text = file_path.read_text(encoding="utf-8")

    sections = re.split(
        r"(?=^#{1,6}\s+)",
        document_text,
        flags=re.MULTILINE,
    )

    chunks = []

    for index, section in enumerate(sections):
        section = section.strip()

        if not section:
            continue

        chunk = DocumentChunk(
            chunk_id=f"{file_path.stem}-{index}",
            source=file_path.name,
            text=section,
        )

        chunks.append(chunk)

    return chunks


def load_knowledge_base(
    knowledge_base_path: Path,
) -> list[DocumentChunk]:
    all_chunks = []

    for file_path in sorted(knowledge_base_path.glob("*.md")):
        file_chunks = chunk_markdown_file(file_path)
        all_chunks.extend(file_chunks)

    return all_chunks