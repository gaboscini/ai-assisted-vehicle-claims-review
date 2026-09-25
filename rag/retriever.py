from dataclasses import dataclass

from rag.embedder import embed_texts
from rag.vector_store import get_collection


@dataclass
class RetrievedChunk:
    text: str
    source: str
    chunk_id: str
    distance: float


def retrieve_chunks(
    question: str,
    top_k: int = 3,
) -> list[RetrievedChunk]:
    if not question.strip():
        raise ValueError("Question cannot be empty.")

    collection = get_collection()
    record_count = collection.count()

    if record_count == 0:
        raise ValueError(
            "The knowledge base has not been indexed."
        )

    query_embedding = embed_texts([question])[0]

    result_count = min(top_k, record_count)

    query_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=result_count,
        include=["documents", "metadatas", "distances"],
    )

    document_groups = query_results.get("documents")
    metadata_groups = query_results.get("metadatas")
    distance_groups = query_results.get("distances")

    if not document_groups or not metadata_groups or not distance_groups:
        raise RuntimeError(
            "The claims guidance index returned an incomplete result."
        )

    documents = document_groups[0] or []
    metadatas = metadata_groups[0] or []
    distances = distance_groups[0] or []

    retrieved_chunks = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances,
    ):
        if not document or not metadata:
            continue
        retrieved_chunks.append(
            RetrievedChunk(
                text=document,
                source=metadata.get("source", "Claims guidance"),
                chunk_id=metadata.get("chunk_id", "guidance"),
                distance=distance,
            )
        )

    if not retrieved_chunks:
        raise RuntimeError(
            "No usable claims guidance was returned for this question."
        )

    return retrieved_chunks
