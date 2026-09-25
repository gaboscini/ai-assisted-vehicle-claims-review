from pathlib import Path

import chromadb


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "claims_review_knowledge"


def get_collection():
    client = chromadb.PersistentClient(
        path=str(DATABASE_PATH)
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    return collection
