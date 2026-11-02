#!/usr/bin/env python3
"""Serve the skin preview and apply the chosen theme, layout, and font."""

import datetime
import difflib
import json
import os
import re
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

def apply_patch(yaml: str, scheme: str, layout: str, font: str, style: dict) -> str:
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
    return run_node(script, {"yaml": yaml, "selection": {"scheme": scheme, "layout": layout, "font": font, "style": style}})

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

def apply(scheme: str, layout: str, font: str, page_size: int, style: dict) -> list[str]:
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
    custom = root / "squirrel.custom.yaml"
    default = root / "default.custom.yaml"
    original = read_config(root, "squirrel.custom.yaml")
    menu_original = read_config(root, "default.custom.yaml")
    if scheme not in scheme_ids(original):
        raise RuntimeError("皮肤不在配置里")
    updated = apply_patch(original, scheme, layout, font, cleaned)
    menu_updated = apply_menu(menu_original, page_size)
    originals = {"squirrel.custom.yaml": original, "default.custom.yaml": menu_original}
    written = {"squirrel.custom.yaml": updated, "default.custom.yaml": menu_updated}
    lines = record_change(root, "保存外观", originals, written)
    if updated == original and menu_updated == menu_original:
        return lines
    if updated != original:
        custom.write_text(updated)
    if menu_updated != menu_original:
        default.write_text(menu_updated)
    try:
        deploy_live(root)
    except Exception:
        if updated != original:
            custom.write_text(original)
        if menu_updated != menu_original:
            default.write_text(menu_original)
        drop_last_record(root)
        raise
    return finish_log(root, lines)

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

def diff_lines(name: str, before: str, after: str) -> list[str]:
    if before == after:
        return [f"{name}：没有变化"]
    lines = [name]
    for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0):
        if line.startswith(("+++", "---", "@@")):
            continue
        lines.append(line)
    return lines

def record_change(root: Path, action: str, originals: dict, updated: dict) -> list[str]:
    changed = {name: text for name, text in originals.items() if updated.get(name, text) != text}
    lines = [action]
    stamp = None
    if changed:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        folder = backup_store(root) / stamp
        folder.mkdir(parents=True)
        for name, text in changed.items():
            (folder / name).write_text(text)
        (folder / "manifest.json").write_text(json.dumps({
            "id": stamp,
            "action": action,
            "files": list(changed),
        }, ensure_ascii=False) + "\n")
        lines.append(f"备份 {stamp}")
        for name, text in changed.items():
            lines.extend(diff_lines(name, text, updated[name]))
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

def preset_before(root: Path, action: str, name: str) -> str:
    for entry in reversed(load_log(root)):
        if action not in (entry.get("action") or "") or not entry.get("id"):
            continue
        path = backup_store(root) / entry["id"] / name
        if path.is_file():
            return path.read_text()
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
        updated = json.loads(run_node(script, {"files": files, "options": options}))
    else:
        updated = dict(files)
    if wanxiang is False:
        updated["rime_ice.custom.yaml"] = preset_before(root, "启用万象语法模型", "rime_ice.custom.yaml")
    action = preset_action(ice, wanxiang)
    lines = record_change(root, action, files, updated)
    if all(files[name] == updated[name] for name in wanted):
        return lines
    for name in wanted:
        dest = (root / name).resolve()
        if dest.parent != root:
            raise RuntimeError("拒绝写出目录")
        dest.write_text(updated[name])
    try:
        deploy_live(root)
    except Exception as error:
        for name, text in files.items():
            (root / name).write_text(text)
        drop_last_record(root)
        built = root / "build" / "default.yaml"
        if built.is_file():
            built.unlink()
        try:
            deploy_live(root)
        except Exception:
            raise RuntimeError("配置已改回，但重新部署没有成功") from error
        raise
    return finish_log(root, lines)

def restore_latest(root: Path) -> list[str]:
    last = next((entry for entry in reversed(load_log(root)) if entry.get("id")), None)
    if not last:
        raise RuntimeError("没有可还原的备份")
    folder = backup_store(root) / last["id"]
    manifest = json.loads((folder / "manifest.json").read_text())
    names = manifest["files"]
    previous = {name: (folder / name).read_text() for name in names}
    current = {}
    for name in names:
        path = root / name
        current[name] = path.read_text() if path.is_file() else ""
    if current == previous:
        return ["撤回上次写入", "已经是上次写入的内容"]
    lines = record_change(root, "撤回上次写入", current, previous)
    for name, text in previous.items():
        dest = (root / name).resolve()
        if dest.parent != root:
            raise RuntimeError("拒绝写出目录")
        dest.write_text(text)
    try:
        deploy_live(root)
    except Exception as error:
        for name, text in current.items():
            (root / name).write_text(text)
        drop_last_record(root)
        built = root / "build" / "default.yaml"
        if built.is_file():
            built.unlink()
        try:
            deploy_live(root)
        except Exception:
            raise RuntimeError("配置已改回，但重新部署没有成功") from error
        raise
    return finish_log(root, lines)

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
        if not custom.is_file():
            custom.write_text("patch:\n  schema_list:\n")
            created = True
            placed["added"].append("default.custom.yaml")
        try:
            set_job(phase="正在部署…")
            return write_presets(True, None)
        except Exception:
            install.undo_ice_files(root, backup, placed["added"], placed["replaced"])
            if created and custom.is_file():
                custom.unlink()
            built = root / "build" / "default.yaml"
            if built.is_file():
                built.unlink()
            try:
                deploy_live(root)
            except Exception:
                raise RuntimeError("雾凇方案已收回，但重新部署没有成功")
            raise
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)


def install_missing_model(root: Path) -> list[str]:
    dest = root / install.MODEL_NAME
    if dest.is_file():
        raise RuntimeError("万象模型已经在，不用再下载")
    partial = root / f"{install.MODEL_NAME}.partial"
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
    if created:
        custom.write_text("patch:\n")
    try:
        set_job(phase="正在部署…")
        return write_presets(None, True)
    except Exception:
        if dest.is_file():
            dest.unlink()
        if created and custom.is_file():
            custom.unlink()
        raise


def run_install(kind: str) -> list[str]:
    with JOB_LOCK:
        if JOB["running"]:
            raise RuntimeError("已经有一个安装在进行")
        if CANCEL.is_set():
            CANCEL.clear()
            raise RuntimeError("已取消")
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
    CANCEL.set()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
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
        route = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length < 0 or length > 1_000_000:
                raise RuntimeError("请求太大")
            body = json.loads(self.rfile.read(length).decode() or "{}")
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
