from pathlib import Path

from rag.chunker import load_knowledge_base
from rag.embedder import embed_texts


project_root = Path(__file__).resolve().parents[2]
knowledge_base_path = project_root / "knowledge_base"

chunks = load_knowledge_base(knowledge_base_path)

if not chunks:
    raise ValueError("No knowledge-base chunks were found.")

chunk_texts = [chunk.text for chunk in chunks]

print(f"Creating embeddings for {len(chunk_texts)} chunks...")

embeddings = embed_texts(chunk_texts)

print("\nEmbedding completed.")
print(f"Number of chunks: {len(chunks)}")
print(f"Number of embeddings: {len(embeddings)}")
print(f"Numbers in each embedding: {len(embeddings[0])}")

print("\nFirst 10 numbers from the first embedding:")

for number in embeddings[0][:10]:
    print(number)
