from rag.retriever import retrieve_chunks


question = input("Ask a question about vehicle claims: ")

results = retrieve_chunks(
    question=question,
    top_k=3,
)

print("\n--- TOP-K RETRIEVAL RESULTS ---\n")

for rank, result in enumerate(results, start=1):
    print("=" * 70)
    print(f"Rank: {rank}")
    print(f"Source: {result.source}")
    print(f"Chunk ID: {result.chunk_id}")
    print(f"Distance: {result.distance:.4f}")
    print("-" * 70)
    print(result.text)
    print()
