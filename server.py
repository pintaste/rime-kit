#!/usr/bin/env python3
"""Serve the skin preview and apply the chosen theme, layout, and font."""

import datetime
import difflib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

import install

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "index.html"
PANEL = ROOT / "panel.mjs"
HOME_RIME = (Path.home() / "Library" / "Rime").resolve()
DEPLOYER = "/Library/Input Methods/Squirrel.app/Contents/MacOS/rime_deployer"
SQUIRREL = "/Library/Input Methods/Squirrel.app/Contents/MacOS/Squirrel"
SHARED = "/Library/Input Methods/Squirrel.app/Contents/SharedSupport"
SESSION_TOKEN = secrets.token_urlsafe(32)

def writable_user_dir() -> Path:
    root = read_user_dir()
    if root == (ROOT / "fixtures").resolve():
        raise RuntimeError("没有找到 ~/Library/Rime。当前是仓库里的示例，不会写入。")
    return root

FONTS = {
    "LXGW ZhenKai Slab GB",
    "LXGW WenKai",
    "PingFang SC",
    "Kaiti SC",
    "Songti SC",
    "Xingkai SC",
}
LAYOUTS = {"linear", "stacked"}
DEFINITION_KEYS = {
    "name",
    "back_color",
    "border_color",
    "text_color",
    "candidate_text_color",
    "label_color",
    "comment_text_color",
    "hilited_back_color",
    "hilited_candidate_back_color",
    "hilited_candidate_text_color",
    "hilited_candidate_label_color",
    "hilited_label_color",
    "hilited_comment_text_color",
    "corner_radius",
    "hilited_corner_radius",
    "border_height",
    "border_width",
    "font_point",
    "label_font_point",
    "font_face",
    "label_font_face",
    "line_spacing",
    "shadow_size",
    "candidate_list_layout",
    "inline_preedit",
    "text_orientation",
}


def yaml_scalar(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./+-]+", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def preset_block(text: str) -> tuple[int, int]:
    mark = "\n  preset_color_schemes:\n"
    start = text.find(mark)
    if start < 0:
        raise RuntimeError("找不到 preset_color_schemes")
    body = start + len(mark)
    end_match = re.search(r"\n  [A-Za-z_#]", text[body:])
    end = body + end_match.start() if end_match else len(text)
    return body, end


def scheme_ids(text: str) -> set[str]:
    body, end = preset_block(text)
    return set(re.findall(r"^    ([A-Za-z0-9_]+):\s*$", text[body:end], re.M))


def replace_style(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^(  style/{re.escape(key)}:\s*)(.*)$", re.M)

    def repl(match: re.Match[str]) -> str:
        comment = ""
        raw = match.group(2)
        hash_at = raw.find(" #")
        if hash_at >= 0:
            comment = raw[hash_at:]
        return match.group(1) + yaml_scalar(value) + comment

    new, count = pattern.subn(repl, text, count=1)
    if count != 1:
        raise RuntimeError(f"找不到 style/{key}")
    return new


def replace_in_scheme(text: str, scheme: str, key: str, value: str) -> str:
    body, end = preset_block(text)
    matches = list(re.finditer(r"^    ([A-Za-z0-9_]+):\s*$", text[body:end], re.M))
    target = next((item for item in matches if item.group(1) == scheme), None)
    if target is None:
        raise RuntimeError(f"找不到皮肤 {scheme}")
    start = body + target.end()
    later = [item for item in matches if item.start() > target.start()]
    stop = body + later[0].start() if later else end
    block = text[start:stop]
    pattern = re.compile(rf"^(      {re.escape(key)}:\s*)(.*)$", re.M)
    if not pattern.search(block):
        return text

    def repl(match: re.Match[str]) -> str:
        comment = ""
        raw = match.group(2)
        hash_at = raw.find(" #")
        if hash_at >= 0:
            comment = raw[hash_at:]
        return match.group(1) + yaml_scalar(value) + comment

    block = pattern.sub(repl, block, count=1)
    return text[:start] + block + text[stop:]


def run_node(script: str, payload: dict) -> str:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        message = ""
        for line in result.stderr.splitlines():
            if line.startswith("Error:"):
                message = line.split(":", 1)[1].strip()
                break
        raise RuntimeError(message or result.stderr.strip() or "补丁失败")
    return result.stdout

def apply_patch(yaml: str, scheme: str, layout: str, font: str, style: dict, definition: Optional[dict] = None) -> str:
    script = f"""
import {{ applyPatch }} from "{PANEL.as_uri()}";
let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {{ raw += chunk; }});
process.stdin.on("end", () => {{
  const body = JSON.parse(raw);
  process.stdout.write(applyPatch(body.yaml, body.selection));
}});
"""
    selection = {"scheme": scheme, "layout": layout, "font": font, "style": style}
    if definition is not None:
        selection["definition"] = definition
    return run_node(script, {"yaml": yaml, "selection": selection})

def apply_menu(yaml: str, page_size: int) -> str:
    script = f"""
import {{ applyMenu }} from "{PANEL.as_uri()}";
let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {{ raw += chunk; }});
process.stdin.on("end", () => {{
  const body = JSON.parse(raw);
  process.stdout.write(applyMenu(body.yaml, body.pageSize));
}});
"""
    return run_node(script, {"yaml": yaml, "pageSize": page_size})

def clean_definition(scheme: str, definition) -> Optional[dict]:
    if definition is None:
        return None
    if not isinstance(definition, dict):
        raise RuntimeError("皮肤定义格式不对")
    if str(definition.get("id", "")) != scheme:
        raise RuntimeError("皮肤定义和选择对不上")
    cleaned = {}
    for key, value in definition.items():
        if key == "id":
            continue
        if key not in DEFINITION_KEYS:
            raise RuntimeError(f"皮肤定义里有不认识的项 {key}")
        if isinstance(value, bool):
            cleaned[key] = "true" if value else "false"
        elif isinstance(value, (int, float)):
            cleaned[key] = str(value)
        elif isinstance(value, str) and len(value) <= 64:
            cleaned[key] = value
        else:
            raise RuntimeError(f"皮肤定义里的 {key} 不是标量")
    cleaned["id"] = scheme
    return cleaned


def apply(scheme: str, layout: str, font: str, page_size: int, style: dict, definition=None) -> list[str]:
    if not re.fullmatch(r"[A-Za-z0-9_]+", scheme):
        raise RuntimeError("皮肤 id 无效")
    if layout not in LAYOUTS:
        raise RuntimeError("排列无效")
    if font not in FONTS:
        raise RuntimeError("字体不在可选列表")
    if not isinstance(page_size, int) or not 1 <= page_size <= 9:
        raise RuntimeError("候选数要在 1 到 9")
    cleaned = {}
    if "inline_preedit" in style:
        cleaned["inline_preedit"] = bool(style["inline_preedit"])
    for key in ("font_point", "label_font_point"):
        if key not in style:
            continue
        value = int(style[key])
        if not 8 <= value <= 32:
            raise RuntimeError("字号超出范围")
        cleaned[key] = value
    root = writable_user_dir()
    original = read_config(root, "squirrel.custom.yaml")
    menu_original = read_config(root, "default.custom.yaml")
    known = scheme_ids(original)
    skin = clean_definition(scheme, definition)
    if scheme not in known and skin is None:
        raise RuntimeError("皮肤不在配置里，也没有可写入的定义")
    updated = apply_patch(original, scheme, layout, font, cleaned, skin)
    menu_updated = apply_menu(menu_original, page_size)
    originals = {
        "squirrel.custom.yaml": original.encode(),
        "default.custom.yaml": menu_original.encode(),
    }
    written = {
        "squirrel.custom.yaml": updated.encode(),
        "default.custom.yaml": menu_updated.encode(),
    }
    return commit_change(root, "保存外观", originals, written)

def deploy_live(root: Path) -> None:
    if root != HOME_RIME:
        return
    env = dict(os.environ)
    env["GLOG_logtostderr"] = "1"
    result = subprocess.run(
        [DEPLOYER, "--build", str(root), SHARED],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        notes = []
        for line in result.stderr.splitlines():
            if line[:1] in ("W", "E") and "] " in line:
                notes.append(line.split("] ", 1)[1])
        raise RuntimeError("重新部署失败：" + ("；".join(notes[-4:]) or "鼠须管没有说明原因"))
    reload = subprocess.run([SQUIRREL, "--reload"], capture_output=True, text=True)
    if reload.returncode != 0:
        raise RuntimeError(reload.stderr.strip() or "重新部署后没有刷新")

def read_user_dir() -> Path:
    raw = os.environ.get("RIME_USER_DIR")
    if raw:
        path = Path(raw).resolve()
        if not path.is_dir():
            raise RuntimeError("RIME_USER_DIR 不是目录")
        return path
    if HOME_RIME.is_dir():
        return HOME_RIME
    return ROOT / "fixtures"

def read_config(root: Path, name: str) -> str:
    path = root / name
    if not path.is_file():
        raise RuntimeError(f"还没有 {name}。先打开一次鼠须管，让它生成这份文件。")
    return path.read_text()

def config_file(name: str) -> Path:
    return read_user_dir() / name

def preset_status() -> dict:
    root = read_user_dir()
    files = {}
    for name in ("default.custom.yaml", "rime_ice.custom.yaml"):
        path = root / name
        files[name] = path.read_text() if path.is_file() else ""
    script = f"""
import {{ presetStatus }} from "{ROOT.joinpath("presets.mjs").as_uri()}";
let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {{ raw += chunk; }});
process.stdin.on("end", () => {{
  const body = JSON.parse(raw);
  process.stdout.write(JSON.stringify(presetStatus(body.files)));
}});
"""
    status = json.loads(run_node(script, {"files": files}))
    status["iceFiles"] = (root / install.SCHEMA_MARK).is_file()
    status["modelFile"] = (root / install.MODEL_NAME).is_file()
    status["example"] = root == (ROOT / "fixtures").resolve()

    return status

def backup_store(root: Path) -> Path:
    if root == HOME_RIME:
        return ROOT / "backups"
    return root / ".rime-kit-backup"

def load_log(root: Path) -> list:
    path = backup_store(root) / "log.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text())

def save_log(root: Path, entries: list) -> None:
    store = backup_store(root)
    store.mkdir(parents=True, exist_ok=True)
    (store / "log.json").write_text(json.dumps(entries[-40:], ensure_ascii=False, indent=2) + "\n")

class Present:
    """File exists but its content is not tracked: binary or too large."""

PRESENT = Present()

def diff_lines(name: str, before, after) -> list[str]:
    if before == after:
        return [f"{name}：没有变化"]
    if before is None:
        return [f"{name}：新增"]
    if after is None:
        return [f"{name}：删除"]
    if after is PRESENT or before is PRESENT:
        return [f"{name}：已更新"]
    lines = [name]
    old = before.decode("utf-8", "replace")
    new = after.decode("utf-8", "replace")
    for line in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0):
        if line.startswith(("+++", "---", "@@")):
            continue
        lines.append(line)
    return lines

def stored_path(store: Path, name: str) -> Path:
    target = (store / name).resolve()
    base = store.resolve()
    if base not in target.parents:
        raise RuntimeError("拒绝写出目录")
    return target

def record_change(root: Path, action: str, originals: dict, updated: dict) -> list[str]:
    names = [name for name in dict.fromkeys([*originals, *updated]) if originals.get(name) != updated.get(name)]
    lines = [action]
    stamp = None
    if names:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        folder = backup_store(root) / stamp
        folder.mkdir(parents=True)
        files = []
        added = []
        for name in names:
            before = originals.get(name)
            if before is None or before is PRESENT:
                added.append(name)
                continue
            target = stored_path(folder, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(before)
            files.append(name)
        (folder / "manifest.json").write_text(json.dumps({
            "id": stamp,
            "action": action,
            "files": files,
            "added": added,
        }, ensure_ascii=False) + "\n")
        lines.append(f"备份 {stamp}")
        for name in names:
            lines.extend(diff_lines(name, originals.get(name), updated.get(name)))
    else:
        lines.append("已经是这样，没有写入")
    entries = load_log(root)
    entries.append({"id": stamp, "action": action, "lines": lines})
    save_log(root, entries)
    return lines

def drop_last_record(root: Path) -> None:
    entries = load_log(root)
    if not entries:
        return
    failed = entries.pop()
    save_log(root, entries)
    if failed.get("id"):
        shutil.rmtree(backup_store(root) / failed["id"], ignore_errors=True)

def finish_log(root: Path, lines: list[str]) -> list[str]:
    if root == HOME_RIME:
        lines.append("已重新部署")
    entries = load_log(root)
    if entries:
        entries[-1]["lines"] = lines
        save_log(root, entries)
    return lines

def config_path(root: Path, name: str) -> Path:
    base = root.resolve()
    dest = (base / name).resolve()
    if dest != base and base not in dest.parents:
        raise RuntimeError("拒绝写出目录")
    return dest


def atomic_write(path: Path, data: bytes) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_files(root: Path, files: dict) -> None:
    for name, data in files.items():
        target = config_path(root, name)
        if data is None:
            target.unlink(missing_ok=True)
            continue
        if data is PRESENT:
            continue
        atomic_write(target, data)


def commit_change(root: Path, action: str, originals: dict, updated: dict, write: bool = True) -> list[str]:
    lines = record_change(root, action, originals, updated)
    changed = {name: value for name, value in updated.items() if originals.get(name) != value}
    if not changed:
        return lines
    previous = {name: originals.get(name) for name in changed}
    try:
        if write:
            write_files(root, changed)
        deploy_live(root)
    except Exception as error:
        try:
            write_files(root, previous)
            built = root / "build" / "default.yaml"
            if built.is_file():
                built.unlink()
            deploy_live(root)
            drop_last_record(root)
        except Exception as recovery_error:
            raise RuntimeError(f"配置恢复失败：{recovery_error}") from error
        raise
    return finish_log(root, lines)

def save_preset_baseline(root: Path, name: str, data: bytes) -> None:
    path = backup_store(root) / "preset-baseline" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, data)


def preset_before(root: Path, action: str, name: str) -> bytes:
    baseline = backup_store(root) / "preset-baseline" / name
    if baseline.is_file():
        return baseline.read_bytes()
    for entry in reversed(load_log(root)):
        if action not in (entry.get("action") or "") or not entry.get("id"):
            continue
        path = backup_store(root) / entry["id"] / name
        if path.is_file():
            return path.read_bytes()
    raise RuntimeError("没有启用前的备份，不能停用")


def preset_action(ice: Optional[bool], wanxiang: Optional[bool]) -> str:
    parts = []
    if ice is True:
        parts.append("启用雾凇拼音")
    elif ice is False:
        parts.append("停用雾凇拼音")
    if wanxiang is True:
        parts.append("启用万象语法模型")
    elif wanxiang is False:
        parts.append("停用万象语法模型")
    if not parts:
        raise RuntimeError("没有要写入的预设")
    return "、".join(parts)


def run_presets(files: dict[str, str], options: dict) -> dict[str, str]:
    script = f"""
import {{ applyPresets }} from "{ROOT.joinpath("presets.mjs").as_uri()}";
let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {{ raw += chunk; }});
process.stdin.on("end", () => {{
  const body = JSON.parse(raw);
  process.stdout.write(JSON.stringify(applyPresets(body.files, body.options)));
}});
"""
    return json.loads(run_node(script, {"files": files, "options": options}))


def write_presets(ice: Optional[bool] = None, wanxiang: Optional[bool] = None) -> list[str]:
    root = writable_user_dir()
    wanted = []
    if ice is not None:
        wanted.append("default.custom.yaml")
    if wanxiang is not None:
        wanted.append("rime_ice.custom.yaml")
    if not wanted:
        raise RuntimeError("没有要写入的预设")
    files = {name: read_config(root, name) for name in wanted}
    options = {}
    if ice is not None:
        options["ice"] = ice
    if wanxiang is True:
        options["wanxiang"] = True
    if options:
        updated = run_presets(files, options)
    else:
        updated = dict(files)
    if wanxiang is False:
        updated["rime_ice.custom.yaml"] = preset_before(root, "启用万象语法模型", "rime_ice.custom.yaml").decode()
    action = preset_action(ice, wanxiang)
    before = {name: files[name].encode() for name in wanted}
    after = {name: updated[name].encode() for name in wanted}
    enabling = wanxiang is True and before["rime_ice.custom.yaml"] != after["rime_ice.custom.yaml"]
    lines = commit_change(root, action, before, after)
    if enabling:
        save_preset_baseline(root, "rime_ice.custom.yaml", before["rime_ice.custom.yaml"])
    return lines

def restore_latest(root: Path) -> list[str]:
    last = next((entry for entry in reversed(load_log(root)) if entry.get("id")), None)
    if not last:
        raise RuntimeError("没有可还原的备份")
    folder = backup_store(root) / last["id"]
    manifest = json.loads((folder / "manifest.json").read_text())
    previous = {}
    for name in manifest.get("files", []):
        previous[name] = stored_path(folder, name).read_bytes()
    for name in manifest.get("added", []):
        previous[name] = None
    if not previous:
        raise RuntimeError("这份备份没有记录文件")
    current = {}
    for name in previous:
        path = root / name
        current[name] = path.read_bytes() if path.is_file() else None
    if current == previous:
        return ["撤回上次写入", "已经是上次写入的内容"]
    return commit_change(root, "撤回上次写入", current, previous)

WRITE_LOCK = threading.Lock()
JOB_LOCK = threading.Lock()
JOB = {"running": False, "phase": "", "received": 0, "total": 0}
CANCEL = threading.Event()


def job_state() -> dict:
    with JOB_LOCK:
        return dict(JOB)


def set_job(**values) -> None:
    with JOB_LOCK:
        JOB.update(values)


def cancelled() -> bool:
    return CANCEL.is_set()


def clone_ice(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    log = dest.parent / "clone.err"
    with log.open("w") as err:
        proc = subprocess.Popen(
            ["git", "clone", "--depth", "1", install.ICE_GIT, str(dest)],
            stdout=subprocess.DEVNULL,
            stderr=err,
        )
        while True:
            try:
                proc.wait(timeout=0.3)
                break
            except subprocess.TimeoutExpired:
                if cancelled():
                    proc.kill()
                    proc.wait()
                    raise RuntimeError("已取消")
    if cancelled():
        raise RuntimeError("已取消")
    if proc.returncode != 0:
        detail = log.read_text().strip()
        raise RuntimeError(detail or "雾凇方案下载失败")


def install_missing_ice(root: Path) -> list[str]:
    if (root / install.SCHEMA_MARK).is_file():
        raise RuntimeError("雾凇方案已经在，不用再装")
    set_job(phase="正在下载雾凇方案…", received=0, total=0)
    scratch = Path(tempfile.mkdtemp(prefix="rime-ice-"))
    backup = Path(tempfile.mkdtemp(prefix="rime-ice-backup-"))
    placed = {"added": [], "replaced": []}
    created = False
    custom = root / "default.custom.yaml"
    try:
        clone_ice(scratch / "src")
        set_job(phase="正在写入雾凇方案…")
        placed = install.place_ice_files(scratch / "src", root, backup)
        created = not custom.is_file()
        if created:
            atomic_write(custom, b"patch:\n  schema_list:\n")
        menu_before = read_config(root, "default.custom.yaml")
        menu_after = run_presets({"default.custom.yaml": menu_before}, {"ice": True})["default.custom.yaml"]
        originals = {name: (backup / name).read_bytes() for name in placed["replaced"]}
        originals.update({name: None for name in placed["added"]})
        originals["default.custom.yaml"] = None if created else menu_before.encode()
        updated = {name: PRESENT for name in [*placed["added"], *placed["replaced"]]}
        updated["default.custom.yaml"] = menu_after.encode()
        atomic_write(custom, menu_after.encode())
        set_job(phase="正在部署…")
        return commit_change(root, "安装雾凇拼音", originals, updated, write=False)
    except Exception as error:
        try:
            install.undo_ice_files(root, backup, placed["added"], placed["replaced"])
            if created and custom.is_file():
                custom.unlink()
            built = root / "build" / "default.yaml"
            if built.is_file():
                built.unlink()
            deploy_live(root)
        except Exception as recovery_error:
            raise RuntimeError(f"雾凇方案恢复失败：{recovery_error}") from error
        raise
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)


def install_missing_model(root: Path) -> list[str]:
    dest = root / install.MODEL_NAME
    if dest.is_file():
        raise RuntimeError("万象模型已经在，不用再下载")
    fd, raw_partial = tempfile.mkstemp(prefix=f".{install.MODEL_NAME}.", suffix=".partial", dir=root)
    os.close(fd)
    partial = Path(raw_partial)
    set_job(phase="正在下载万象语法模型…", received=0, total=install.MODEL_BYTES)

    def progress(received: int, total: int) -> None:
        set_job(phase="正在下载万象语法模型…", received=received, total=total)

    try:
        install.download(install.MODEL_URL, partial, install.MODEL_BYTES, progress, cancelled)
        os.replace(partial, dest)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    custom = root / "rime_ice.custom.yaml"
    created = not custom.is_file()
    before = b"patch:\n" if created else custom.read_bytes()
    try:
        if created:
            atomic_write(custom, before)
        updated = run_presets({"rime_ice.custom.yaml": before.decode()}, {"wanxiang": True})["rime_ice.custom.yaml"]
        atomic_write(custom, updated.encode())
        set_job(phase="正在部署…")
        lines = commit_change(
            root,
            "安装万象语法模型",
            {install.MODEL_NAME: None, "rime_ice.custom.yaml": None if created else before},
            {install.MODEL_NAME: PRESENT, "rime_ice.custom.yaml": updated.encode()},
            write=False,
        )
    except Exception:
        if dest.is_file():
            dest.unlink()
        if created and custom.is_file():
            custom.unlink()
        raise
    save_preset_baseline(root, "rime_ice.custom.yaml", before)
    return lines


def run_install(kind: str) -> list[str]:
    with JOB_LOCK:
        if JOB["running"]:
            raise RuntimeError("已经有一个安装在进行")
        CANCEL.clear()
        JOB.update(running=True, phase="正在准备…", received=0, total=0)
    try:
        root = writable_user_dir()
        if kind == "ice":
            return install_missing_ice(root)
        if kind == "model":
            return install_missing_model(root)
        raise RuntimeError("没有要安装的项目")
    finally:
        CANCEL.clear()
        set_job(running=False)


def cancel_install() -> None:
    with JOB_LOCK:
        if not JOB["running"]:
            return
    CANCEL.set()


class Handler(BaseHTTPRequestHandler):
    def _valid_host(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in {
            f"127.0.0.1:{port}",
            f"localhost:{port}",
        }

    def _valid_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        port = self.server.server_address[1]
        return origin in {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }

    def do_GET(self) -> None:
        if not self._valid_host():
            self._json(403, {"ok": False, "error": "拒绝未知来源"})
            return
        path = self.path.split("?", 1)[0]
        if path == "/session":
            self._json(200, {"ok": True, "token": SESSION_TOKEN})
            return
        if path == "/status":
            try:
                self._json(200, {"ok": True, **preset_status()})
            except RuntimeError as error:
                self._json(400, {"ok": False, "error": str(error)})
            return
        if path == "/log":
            try:
                self._json(200, {"ok": True, "entries": load_log(read_user_dir())})
            except RuntimeError as error:
                self._json(400, {"ok": False, "error": str(error)})
            return
        if path == "/install-progress":
            self._json(200, {"ok": True, **job_state()})
            return
        if path in ("/config.yaml", "/default.yaml", "/ice.yaml"):
            name = {
                "/config.yaml": "squirrel.custom.yaml",
                "/default.yaml": "default.custom.yaml",
                "/ice.yaml": "rime_ice.custom.yaml",
            }[path]
            try:
                file = config_file(name)
            except RuntimeError as error:
                self._json(400, {"ok": False, "error": str(error)})
                return
            if not file.is_file():
                self.send_error(404)
                return
            data = file.read_bytes()
            self._send(200, "text/yaml; charset=utf-8", data)
            return
        files = {
            "/": (HTML, "text/html; charset=utf-8"),
            "/index.html": (HTML, "text/html; charset=utf-8"),
            "/panel.mjs": (PANEL, "text/javascript; charset=utf-8"),
            "/presets.mjs": (ROOT / "presets.mjs", "text/javascript; charset=utf-8"),
        }
        item = files.get(path)
        if item is None:
            self.send_error(404)
            return
        file, content_type = item
        self._send(200, content_type, file.read_bytes())

    def _send(self, status: int, content_type: str, data: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        if not self._valid_host() or not self._valid_origin():
            self._json(403, {"ok": False, "error": "拒绝跨站请求"})
            return
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._json(415, {"ok": False, "error": "请求必须使用 application/json"})
            return
        token = self.headers.get("X-Rime-Kit-Token", "")
        if not secrets.compare_digest(token, SESSION_TOKEN):
            self._json(403, {"ok": False, "error": "写入令牌无效"})
            return
        route = self.path.split("?", 1)[0]
        locked = False
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length < 0 or length > 1_000_000:
                raise RuntimeError("请求太大")
            body = json.loads(self.rfile.read(length).decode() or "{}")
            if route in {"/presets", "/restore", "/apply", "/install"}:
                locked = WRITE_LOCK.acquire(blocking=False)
                if not locked:
                    self._json(409, {"ok": False, "error": "另一个写入正在进行"})
                    return
            if route == "/presets":
                lines = write_presets(body["ice"] if "ice" in body else None, body["wanxiang"] if "wanxiang" in body else None)
            elif route == "/restore":
                lines = restore_latest(writable_user_dir())
            elif route == "/apply":
                lines = apply(
                    str(body["scheme"]),
                    str(body["layout"]),
                    str(body["font"]),
                    int(body["pageSize"]),
                    body.get("style") or {},
                    body.get("definition"),
                )
            elif route == "/install":
                if body.get("ice"):
                    lines = run_install("ice")
                elif body.get("model"):
                    lines = run_install("model")
                else:
                    raise RuntimeError("没有要安装的项目")
            elif route == "/install-cancel":
                cancel_install()
                lines = ["正在取消…"]
            else:
                self.send_error(404)
                return
            message = lines[0] if lines else "完成"
        except Exception as error:
            self._json(400, {"ok": False, "error": str(error)})
            return
        finally:
            if locked:
                WRITE_LOCK.release()
        self._json(200, {"ok": True, "message": message, "log": lines})

    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        print(fmt % args)


if __name__ == "__main__":
    print("rime-skin-server listening on 127.0.0.1:8766", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
