"""Install missing rime-ice files and the Wanxiang grammar model."""

import shutil
import urllib.request
from pathlib import Path

ICE_GIT = "https://github.com/iDvel/rime-ice.git"
MODEL_URL = "https://github.com/amzxyz/RIME-LMDG/releases/download/LTS/wanxiang-lts-zh-hans.gram"
MODEL_NAME = "wanxiang-lts-zh-hans.gram"
MODEL_BYTES = 418078764
SCHEMA_MARK = "rime_ice.schema.yaml"

SKIP_DIRS = {".git", ".github", "others", "build"}
SKIP_NAMES = {".gitignore", "LICENSE", "README.md", "AGENTS.md"}
KEEP_IF_PRESENT = {"custom_phrase.txt", "squirrel.yaml", "weasel.yaml"}
NEVER = {
    "squirrel.custom.yaml",
    "weasel.custom.yaml",
    "default.custom.yaml",
    "rime_ice.custom.yaml",
    "user.yaml",
    "installation.yaml",
}


def ice_action(relative: str, exists: bool) -> str:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return "skip"
    if path.parts[0] in SKIP_DIRS or path.name in SKIP_NAMES or path.name in NEVER:
        return "skip"
    if path.name.endswith(".custom.yaml") or path.suffix == ".gram":
        return "skip"
    if path.name in KEEP_IF_PRESENT:
        return "skip" if exists else "add"
    return "replace" if exists else "add"


def place_ice_files(source: Path, dest: Path, backup: Path) -> dict:
    added = []
    replaced = []
    root = dest.resolve()
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source).as_posix()
        target = (dest / relative).resolve()
        if root not in target.parents:
            raise RuntimeError("拒绝写出目录")
        action = ice_action(relative, target.is_file())
        if action == "skip":
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if action == "replace":
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            replaced.append(relative)
        else:
            added.append(relative)
        shutil.copy2(path, target)
    if not (dest / SCHEMA_MARK).is_file():
        raise RuntimeError("下载的雾凇方案里没有 rime_ice.schema.yaml")
    return {"added": added, "replaced": replaced}


def undo_ice_files(dest: Path, backup: Path, added: list, replaced: list) -> None:
    for relative in added:
        target = dest / relative
        if target.is_file():
            target.unlink()
    for relative in replaced:
        shutil.copy2(backup / relative, dest / relative)


def download(url: str, dest: Path, expected: int, progress, cancelled) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "rime-kit"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            if expected and total and total != expected:
                raise RuntimeError(f"模型大小和配方不一致：{total}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            received = 0
            with dest.open("wb") as handle:
                while True:
                    if cancelled():
                        raise RuntimeError("已取消")
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    received += len(chunk)
                    progress(received, total or expected)
        if expected and received != expected:
            raise RuntimeError(f"下载不完整：{received}")
    except Exception:
        dest.unlink(missing_ok=True)
        raise
