"""Version the whole asset directory so relative JavaScript imports stay in sync."""

from hashlib import sha256
from pathlib import Path

STATIC_DIRECTORY = Path(__file__).resolve().parents[1] / "static"


def asset_version(directory: Path) -> str:
    digest = sha256()
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix in {".js", ".css"}:
            digest.update(path.relative_to(directory).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


STATIC_ASSET_PREFIX = f"/assets/{asset_version(STATIC_DIRECTORY)}"
