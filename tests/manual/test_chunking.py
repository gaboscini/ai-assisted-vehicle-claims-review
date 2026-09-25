from pathlib import Path

from rag.chunker import load_knowledge_base


project_root = Path(__file__).resolve().parents[2]
knowledge_base_path = project_root / "knowledge_base"

chunks = load_knowledge_base(knowledge_base_path)

print(f"\nTotal chunks created: {len(chunks)}\n")

for chunk in chunks:
    print("=" * 70)
    print(f"Chunk ID: {chunk.chunk_id}")
    print(f"Source: {chunk.source}")
    print("-" * 70)
    print(chunk.text)
    print()
