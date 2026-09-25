from dataclasses import dataclass

from ollama import chat

from rag.retriever import RetrievedChunk, retrieve_chunks


GENERATION_MODEL = "gemma3:4b"


@dataclass
class RAGResponse:
    answer: str
    retrieved_chunks: list[RetrievedChunk]


def answer_question(
    question: str,
    top_k: int = 3,
) -> RAGResponse:
    retrieved_chunks = retrieve_chunks(
        question=question,
        top_k=top_k,
    )

    context_sections = []

    for chunk in retrieved_chunks:
        context_sections.append(
            f"""
Source: {chunk.source}
Chunk ID: {chunk.chunk_id}

{chunk.text}
""".strip()
        )

    context = "\n\n---\n\n".join(context_sections)

    system_prompt = """
You are the Claims Help assistant for a vehicle insurance claims portal.

Answer using only the supplied knowledge-base context.

Rules:
- Use clear, professional, customer-safe language.
- Do not mention language models, retrieval systems, local infrastructure,
  prototypes, or implementation details.
- Do not invent missing policy terms or business rules.
- If the answer is not in the context, say that the knowledge base
  does not contain enough information.
- Do not approve or reject an insurance claim.
- Do not reveal internal claims-officer notes or imply that a confidence
  score is an approval probability.
- Answer every part of the question and include all required items explicitly
  stated in the supplied context.
- Remind the user that final coverage and claim decisions depend on the
  applicable policy and an authorized claims officer when relevant.
- Keep the answer clear and concise.
"""

    user_prompt = f"""
KNOWLEDGE-BASE CONTEXT

{context}

USER QUESTION

{question}
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    answer = ""
    last_error: Exception | None = None
    for _ in range(2):
        try:
            response = chat(
                model=GENERATION_MODEL,
                messages=messages,
                options={"temperature": 0},
            )
        except Exception as error:
            last_error = error
            continue

        message = getattr(response, "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            answer = content.strip()
            break

        last_error = RuntimeError(
            "The claims guidance service returned an empty response."
        )

    if not answer:
        raise RuntimeError(
            "Claims guidance is temporarily unavailable. Please try again."
        ) from last_error

    return RAGResponse(
        answer=answer,
        retrieved_chunks=retrieved_chunks,
    )
