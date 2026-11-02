import os
import shutil
import tempfile
from pathlib import Path

import server

os.environ.pop("RIME_USER_DIR", None)
os.environ.pop("RIME_ALLOW_HOME", None)
os.environ.pop("RIME_DEPLOY", None)
if server.read_user_dir() != server.HOME_RIME:
    raise SystemExit("did not read the home rime dir")

fixtures = Path(__file__).resolve().parent / "fixtures"
with tempfile.TemporaryDirectory(prefix="rime-kit-") as raw:
    dest = Path(raw)
    for name in ("default.custom.yaml", "rime_ice.custom.yaml", "squirrel.custom.yaml"):
        shutil.copy(fixtures / name, dest / name)
    os.environ["RIME_USER_DIR"] = raw
    server.write_presets(True, True)
    ice = (dest / "rime_ice.custom.yaml").read_text()
    menu = (dest / "default.custom.yaml").read_text()
    if "wanxiang-lts-zh-hans" not in ice:
        raise SystemExit("model not written")
    if "schema: rime_ice" not in menu or "schema: luna_pinyin" not in menu:
        raise SystemExit("schema not written")
    before = (fixtures / "rime_ice.custom.yaml").read_text()
    server.write_presets(False, None)
    menu = (dest / "default.custom.yaml").read_text()
    if "schema: rime_ice" in menu or "schema: luna_pinyin" not in menu:
        raise SystemExit("schema disable failed")
    server.write_presets(None, False)
    if (dest / "rime_ice.custom.yaml").read_text() != before:
        raise SystemExit("model disable did not restore the previous file")
    if server.HOME_RIME in dest.parents or dest == server.HOME_RIME:
        raise SystemExit("wrote inside the home rime dir")

os.environ["RIME_USER_DIR"] = str(fixtures)
try:
    server.writable_user_dir()
except RuntimeError as error:
    if "示例" not in str(error):
        raise
else:
    raise SystemExit("fixtures were writable")

with tempfile.TemporaryDirectory(prefix="rime-kit-empty-") as raw:
    os.environ["RIME_USER_DIR"] = raw
    try:
        server.apply("macos_dark", "stacked", "PingFang SC", 5, {})
    except RuntimeError as error:
        if "squirrel.custom.yaml" not in str(error):
            raise
    else:
        raise SystemExit("missing config was accepted")

with tempfile.TemporaryDirectory(prefix="rime-kit-recover-") as raw:
    root = Path(raw)
    for name in ("default.custom.yaml", "rime_ice.custom.yaml", "squirrel.custom.yaml"):
        shutil.copy(fixtures / name, root / name)
    os.environ["RIME_USER_DIR"] = raw
    original = (root / "squirrel.custom.yaml").read_text()
    deploy_calls = []
    real_deploy = server.deploy_live

    def fail_once(path):
        deploy_calls.append(path)
        if len(deploy_calls) == 1:
            (path / "build").mkdir()
            (path / "build" / "default.yaml").write_text("bad build")
            raise RuntimeError("build failed")

    server.deploy_live = fail_once
    try:
        try:
            server.apply("macos_dark", "linear", "PingFang SC", 8, {})
        except RuntimeError as error:
            if "build failed" not in str(error):
                raise
        else:
            raise SystemExit("failed deploy was accepted")
    finally:
        server.deploy_live = real_deploy
    if (root / "squirrel.custom.yaml").read_text() != original:
        raise SystemExit("failed deploy did not restore config")
    if (root / "build" / "default.yaml").exists():
        raise SystemExit("failed deploy left bad build")
    if len(deploy_calls) != 2:
        raise SystemExit("restored config was not deployed")

print("isolated ok")
