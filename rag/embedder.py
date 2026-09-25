from ollama import embed


EMBEDDING_MODEL = "embeddinggemma"


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts or any(not text.strip() for text in texts):
        raise ValueError("Embedding input cannot be empty.")

    last_error: Exception | None = None
    for _ in range(2):
        try:
            response = embed(
                model=EMBEDDING_MODEL,
                input=texts,
            )
        except Exception as error:
            last_error = error
            continue

        embeddings = getattr(response, "embeddings", None)
        if (
            embeddings
            and len(embeddings) == len(texts)
            and all(vector for vector in embeddings)
        ):
            return embeddings

        last_error = RuntimeError(
            "The embedding service returned an empty response."
        )

    raise RuntimeError(
        "Claims guidance could not create a search representation."
    ) from last_error
