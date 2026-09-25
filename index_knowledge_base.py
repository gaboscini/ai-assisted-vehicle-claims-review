from pathlib import Path

from rag.chunker import load_knowledge_base
from rag.embedder import embed_texts
from rag.vector_store import get_collection


project_root = Path(__file__).parent
knowledge_base_path = project_root / "knowledge_base"

print("Loading and chunking documents...")

chunks = load_knowledge_base(knowledge_base_path)

if not chunks:
    raise ValueError("No knowledge-base chunks were found.")

print(f"Found {len(chunks)} chunks.")
print("Creating embeddings...")

chunk_texts = [chunk.text for chunk in chunks]
embeddings = embed_texts(chunk_texts)

chunk_ids = [chunk.chunk_id for chunk in chunks]

metadata = [
    {
        "source": chunk.source,
        "chunk_id": chunk.chunk_id,
    }
    for chunk in chunks
]

print("Storing chunks in ChromaDB...")

collection = get_collection()

existing_ids = collection.get()["ids"]
if existing_ids:
    collection.delete(ids=existing_ids)
    print(f"Removed {len(existing_ids)} existing records.")

collection.upsert(
    ids=chunk_ids,
    documents=chunk_texts,
    embeddings=embeddings,
    metadatas=metadata,
)

print("\nIndexing completed.")
print(f"Records stored in ChromaDB: {collection.count()}")
