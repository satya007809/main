"""
claude_bridge.py — run this INSIDE Maya (Script Editor, Python tab, or userSetup.py).

Opens a small TCP server on 127.0.0.1:7005 that accepts Python code from the
maya-mcp server (Claude Code) and executes it on Maya's main thread, returning
stdout + the value of a variable named `result` as JSON.

Protocol (both directions): 8-byte big-endian length prefix + UTF-8 JSON body.
    request : {"code": "<python source>"}
    response: {"ok": true, "stdout": "...", "result": <json-able or repr string>}
              {"ok": false, "error": "<traceback text>"}

Usage inside Maya:
    import claude_bridge; claude_bridge.start()        # default port 7005
    claude_bridge.stop()

Only binds to localhost. Anything that can reach this port can run code in Maya,
so do not change the host to 0.0.0.0 on a shared network.
"""
import io
import json
import socket
import struct
import threading
import traceback
import contextlib

try:
    import maya.utils as mutils
    import maya.cmds as cmds
except ImportError:  # imported outside Maya (e.g. for syntax checks)
    mutils = None
    cmds = None

HOST = "127.0.0.1"
PORT = 7005

_server_sock = None
_thread = None
_running = False
# One persistent namespace so Claude can define helpers in one call and reuse them.
_namespace = {"__name__": "__claude_bridge__"}


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf += chunk
    return buf


def _recv_msg(sock):
    (length,) = struct.unpack(">Q", _recv_exact(sock, 8))
    return json.loads(_recv_exact(sock, length).decode("utf-8"))


def _send_msg(sock, obj):
    body = json.dumps(obj, default=repr).encode("utf-8")
    sock.sendall(struct.pack(">Q", len(body)) + body)


def _execute(code):
    """Runs on Maya's main thread. Captures stdout; returns the `result` variable."""
    out = io.StringIO()
    _namespace.pop("result", None)
    try:
        with contextlib.redirect_stdout(out):
            exec(compile(code, "<claude>", "exec"), _namespace)
        result = _namespace.get("result")
        try:
            json.dumps(result)
        except (TypeError, ValueError):
            result = repr(result)
        return {"ok": True, "stdout": out.getvalue(), "result": result}
    except Exception:
        return {"ok": False, "stdout": out.getvalue(), "error": traceback.format_exc()}


def _handle_client(conn):
    with conn:
        try:
            req = _recv_msg(conn)
            code = req.get("code", "")
            if mutils is not None:
                resp = mutils.executeInMainThreadWithResult(_execute, code)
            else:
                resp = _execute(code)
        except Exception:
            resp = {"ok": False, "error": traceback.format_exc()}
        try:
            _send_msg(conn, resp)
        except OSError:
            pass


def _serve():
    global _running
    while _running:
        try:
            conn, _ = _server_sock.accept()
        except OSError:
            break
        threading.Thread(target=_handle_client, args=(conn,), daemon=True).start()


def start(port=PORT, host=HOST):
    """Start the bridge. Safe to call twice; the second call is a no-op."""
    global _server_sock, _thread, _running
    if _running:
        print("[claude_bridge] already running on %s:%d" % (host, port))
        return
    _server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _server_sock.bind((host, port))
    _server_sock.listen(5)
    _running = True
    _thread = threading.Thread(target=_serve, daemon=True)
    _thread.start()
    print("[claude_bridge] listening on %s:%d — Claude Code can now drive Maya" % (host, port))


def stop():
    global _running, _server_sock
    _running = False
    if _server_sock:
        try:
            _server_sock.close()
        except OSError:
            pass
        _server_sock = None
    print("[claude_bridge] stopped")


if __name__ == "__main__" and cmds is not None:
    start()
