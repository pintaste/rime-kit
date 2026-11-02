import json
import os
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

import server


fixtures = Path(__file__).resolve().parent / "fixtures"


def request_status(request: urllib.request.Request) -> int:
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def test_cross_site_write_is_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="rime-kit-http-") as raw:
        root = Path(raw)
        for name in ("default.custom.yaml", "rime_ice.custom.yaml", "squirrel.custom.yaml"):
            shutil.copy(fixtures / name, root / name)
        before = (root / "default.custom.yaml").read_text()
        os.environ["RIME_USER_DIR"] = raw
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        port = httpd.server_address[1]
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/presets",
                data=b'{"ice":true}',
                method="POST",
                headers={
                    "Content-Type": "text/plain",
                    "Origin": "https://evil.example",
                },
            )
            status = request_status(request)
            if status not in (403, 415):
                raise SystemExit(f"cross-site write returned {status}")
            if (root / "default.custom.yaml").read_text() != before:
                raise SystemExit("cross-site write changed config")

            bad_host = urllib.request.Request(
                f"http://127.0.0.1:{port}/session",
                headers={"Host": "evil.example"},
            )
            if request_status(bad_host) != 403:
                raise SystemExit("unknown Host was accepted")

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/session", timeout=5) as response:
                token = json.load(response)["token"]
            def trusted_request() -> urllib.request.Request:
                return urllib.request.Request(
                    f"http://127.0.0.1:{port}/presets",
                    data=b'{"ice":true}',
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "Origin": f"http://127.0.0.1:{port}",
                        "X-Rime-Kit-Token": token,
                    },
                )

            server.WRITE_LOCK.acquire()
            try:
                if request_status(trusted_request()) != 409:
                    raise SystemExit("concurrent write was accepted")
            finally:
                server.WRITE_LOCK.release()
            if (root / "default.custom.yaml").read_text() != before:
                raise SystemExit("busy write changed config")

            if request_status(trusted_request()) != 200:
                raise SystemExit("same-origin write was rejected")
            if "schema: rime_ice" not in (root / "default.custom.yaml").read_text():
                raise SystemExit("same-origin write did not change config")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()
            os.environ.pop("RIME_USER_DIR", None)


if __name__ == "__main__":
    test_cross_site_write_is_rejected()
    print("http ok")
