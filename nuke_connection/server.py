"""
Nuke Server - Run this INSIDE Nuke 17.0's Script Editor to accept external connections.

Usage (in Nuke's Script Editor):
    >>> import sys
    >>> sys.path.append('/path/to/nuke-17-exploration')
    >>> from nuke_connection.server import start_server
    >>> start_server(port=50007)

This starts a threaded TCP server that listens for JSON-encoded Python commands
and executes them safely in Nuke's main thread.
"""

import socket
import threading
import json
import traceback

# These will only be available when running inside Nuke
try:
    import nuke
    IN_NUKE = True
except ImportError:
    IN_NUKE = False


def _execute_in_nuke(code):
    """Execute code string in Nuke and return the result."""
    local_vars = {}
    try:
        # Try eval first (for expressions that return a value)
        result = eval(code, {"nuke": nuke, "__builtins__": __builtins__}, local_vars)
        return {"status": "ok", "result": str(result)}
    except SyntaxError:
        # Fall back to exec (for statements)
        try:
            exec(code, {"nuke": nuke, "__builtins__": __builtins__}, local_vars)
            return {"status": "ok", "result": local_vars.get("result", "executed")}
        except Exception as e:
            return {"status": "error", "message": f"{type(e).__name__}: {e}",
                    "traceback": traceback.format_exc()}
    except Exception as e:
        return {"status": "error", "message": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc()}


def _handle_client(conn, addr):
    """Handle a single client connection."""
    print(f"[NukeServer] Client connected from {addr}")
    try:
        while True:
            data = conn.recv(65536)
            if not data:
                break

            try:
                request = json.loads(data.decode("utf-8").strip())
            except json.JSONDecodeError:
                # Treat raw text as code to execute
                request = {"type": "execute", "code": data.decode("utf-8").strip()}

            if request.get("type") == "disconnect":
                break

            code = request.get("code", "")
            if not code:
                response = {"status": "error", "message": "No code provided"}
            elif IN_NUKE:
                # Execute in Nuke's main thread for thread safety
                response = nuke.executeInMainThreadWithResult(
                    _execute_in_nuke, args=(code,)
                )
            else:
                response = _execute_in_nuke(code)

            conn.sendall(json.dumps(response).encode("utf-8") + b"\n")
    except Exception as e:
        print(f"[NukeServer] Client error: {e}")
    finally:
        conn.close()
        print(f"[NukeServer] Client {addr} disconnected")


def start_server(host="0.0.0.0", port=50007):
    """Start the Nuke command server on a background thread."""
    def _server_loop():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(5)
        print(f"[NukeServer] Listening on {host}:{port}")
        print("[NukeServer] Waiting for external connections...")

        while True:
            conn, addr = server.accept()
            client_thread = threading.Thread(
                target=_handle_client, args=(conn, addr), daemon=True
            )
            client_thread.start()

    thread = threading.Thread(target=_server_loop, daemon=True)
    thread.start()
    print(f"[NukeServer] Server started on port {port}")
    return thread
