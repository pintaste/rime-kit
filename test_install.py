import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import install


def test_rules():
    assert install.ice_action("lua/foo.lua", False) == "add"
    assert install.ice_action("lua/foo.lua", True) == "replace"
    assert install.ice_action("custom_phrase.txt", True) == "skip"
    assert install.ice_action("custom_phrase.txt", False) == "add"
    assert install.ice_action("squirrel.yaml", True) == "skip"
    assert install.ice_action("squirrel.custom.yaml", False) == "skip"
    assert install.ice_action("default.custom.yaml", False) == "skip"
    assert install.ice_action("others/recipes/grammar.recipe.yaml", False) == "skip"
    assert install.ice_action("README.md", False) == "skip"
    assert install.ice_action("../secret", False) == "skip"


def test_place_and_undo():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        source = root / "src"
        dest = root / "rime"
        backup = root / "backup"
        (source / "lua").mkdir(parents=True)
        (source / "lua" / "foo.lua").write_text("new")
        (source / "custom_phrase.txt").write_text("upstream")
        (source / "rime_ice.schema.yaml").write_text("schema")
        (source / "squirrel.custom.yaml").write_text("nope")
        dest.mkdir()
        (dest / "lua").mkdir()
        (dest / "lua" / "foo.lua").write_text("old")
        (dest / "custom_phrase.txt").write_text("mine")
        placed = install.place_ice_files(source, dest, backup)
        assert (dest / "lua" / "foo.lua").read_text() == "new"
        assert (dest / "custom_phrase.txt").read_text() == "mine"
        assert not (dest / "squirrel.custom.yaml").exists()
        assert "lua/foo.lua" in placed["replaced"]
        assert "rime_ice.schema.yaml" in placed["added"]
        install.undo_ice_files(dest, backup, placed["added"], placed["replaced"])
        assert (dest / "lua" / "foo.lua").read_text() == "old"
        assert not (dest / "rime_ice.schema.yaml").exists()

def test_place_failure_undoes_partial():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        source = root / "src"
        dest = root / "rime"
        backup = root / "backup"
        (source / "lua").mkdir(parents=True)
        (source / "lua" / "partial.lua").write_text("partial")
        dest.mkdir()
        try:
            install.place_ice_files(source, dest, backup)
        except RuntimeError as error:
            assert "rime_ice.schema.yaml" in str(error)
        else:
            raise SystemExit("invalid package was accepted")
        assert not (dest / "lua" / "partial.lua").exists()



def test_cancel_removes_partial():
    payload = b"abcdef"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        with tempfile.TemporaryDirectory() as raw:
            dest = Path(raw) / "model.gram.partial"
            try:
                install.download(
                    f"http://127.0.0.1:{port}/model",
                    dest,
                    len(payload) + 1,
                    lambda received, total: None,
                    lambda: False,
                )
            except RuntimeError as error:
                assert "不一致" in str(error) or "不完整" in str(error)
            else:
                raise SystemExit("size mismatch was accepted")
            assert not dest.exists()
    finally:
        server.shutdown()


if __name__ == "__main__":
    test_rules()
    test_place_and_undo()
    test_place_failure_undoes_partial()
    test_cancel_removes_partial()
    print("install ok")
