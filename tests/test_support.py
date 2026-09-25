import shutil
import uuid
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parent / ".runtime"


def create_runtime_directory() -> Path:
    path = RUNTIME_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path


def remove_runtime_directory(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
