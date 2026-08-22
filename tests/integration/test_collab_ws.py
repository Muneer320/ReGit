"""Live-server WebSocket relay proof: two REAL websocket clients over a live
uvicorn server (avoids Starlette TestClient's single-socket concurrent-WebSocket
limitation, which gave a false hang — the real uvicorn server relays fine)."""
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest
import websockets.sync.client as ws_sync

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.src.api.main import app  # noqa: E402
from backend.src.core.collaboration.rooms import CollabHub  # noqa: E402
from backend.src.core.objects.store import ObjectStore  # noqa: E402


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def live_server():
    """Fresh temp store on the app + real uvicorn on a free port."""
    d = tempfile.mkdtemp()
    store = ObjectStore(d)
    app.state.store = store
    app.state.collab_hub = CollabHub(store)
    blob = store.put_blob("md", b"shared seed")
    store.commit([], blob, "art_ws", "root", "muneer", kind="md",
                 author_date="2026-01-01T00:00:00+00:00")

    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.src.api.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(Path(__file__).resolve().parents[2]),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{base}/api/health", timeout=1)
            break
        except Exception:
            time.sleep(0.25)
    yield f"ws://127.0.0.1:{port}"
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def test_live_two_clients_relay(live_server):
    """userA and userB connect; A requests a commit; B must receive the same
    'committed' broadcast (commit id identical on both)."""
    uri = live_server
    with ws_sync.connect(f"{uri}/collaborate/art_ws?branch=main&user=userA") as a:
        with ws_sync.connect(f"{uri}/collaborate/art_ws?branch=main&user=userB") as b:
            a.recv()  # binary sync step1 from server
            b.recv()  # binary sync step1 from server

            a.send('{"type":"presence_ping"}')
            msg = a.recv()
            assert '"presence"' in msg

            a.send('{"type":"commit_request","message":"live save"}')
            got_a, got_b = None, None
            for _ in range(6):
                try:
                    m = a.recv(timeout=2)
                    if '"committed"' in m:
                        got_a = m
                        break
                except Exception:
                    break
            for _ in range(6):
                try:
                    m = b.recv(timeout=2)
                    if '"committed"' in m:
                        got_b = m
                        break
                except Exception:
                    break
            assert got_a is not None, "A never saw its own 'committed'"
            assert got_b is not None, "B never received the 'committed' broadcast"
            cid_a = json.loads(got_a)["commit_id"]
            cid_b = json.loads(got_b)["commit_id"]
            assert cid_a == cid_b