from rag.rag_service import answer_question


question = input("Ask a question about vehicle claims: ")

response = answer_question(
    question=question,
    top_k=3,
)

print("\n--- RAG ANSWER ---\n")
print(response.answer)

print("\n--- RETRIEVED SOURCES ---\n")

for rank, chunk in enumerate(
    response.retrieved_chunks,
    start=1,
):
    print(
        f"{rank}. {chunk.source} "
        f"({chunk.chunk_id}) "
        f"distance={chunk.distance:.4f}"
    )
