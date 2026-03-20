"""
NukeConnector - Socket-based connection to a running Nuke 17.0 instance.

Usage:
    1. Inside Nuke's Script Editor, run the server:
       >>> from nuke_connection.server import start_server
       >>> start_server(port=50007)

    2. From an external Python script:
       >>> from nuke_connection import NukeConnector
       >>> conn = NukeConnector(host="localhost", port=50007)
       >>> conn.connect()
       >>> result = conn.execute("nuke.createNode('Blur')")
       >>> print(result)
       >>> conn.close()
"""

import socket
import json
import time


class NukeConnector:
    """Bidirectional socket client for communicating with a running Nuke instance."""

    def __init__(self, host="localhost", port=50007, timeout=10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._socket = None
        self._connected = False

    @property
    def connected(self):
        return self._connected

    def connect(self):
        """Establish a TCP connection to the Nuke server."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.host, self.port))
            self._connected = True
            print(f"[NukeConnector] Connected to Nuke at {self.host}:{self.port}")
            return True
        except ConnectionRefusedError:
            print(
                f"[NukeConnector] Connection refused. Is the Nuke server running on "
                f"{self.host}:{self.port}?"
            )
            print("[NukeConnector] Start the server inside Nuke with:")
            print("    from nuke_connection.server import start_server")
            print(f"    start_server(port={self.port})")
            self._connected = False
            return False
        except Exception as e:
            print(f"[NukeConnector] Connection error: {e}")
            self._connected = False
            return False

    def execute(self, code):
        """Send Python code to Nuke for execution and return the result."""
        if not self._connected:
            raise RuntimeError("Not connected to Nuke. Call connect() first.")

        payload = json.dumps({"type": "execute", "code": code})
        self._socket.sendall(payload.encode("utf-8") + b"\n")

        # Receive response
        response = self._receive()
        try:
            result = json.loads(response)
            if result.get("status") == "error":
                raise RuntimeError(f"Nuke execution error: {result.get('message')}")
            return result.get("result")
        except json.JSONDecodeError:
            return response

    def create_node(self, node_type, **knobs):
        """Create a node in Nuke with optional knob values."""
        knob_args = ", ".join(f"{k}={v!r}" for k, v in knobs.items())
        code = f"nuke.createNode('{node_type}', '{knob_args}')" if knob_args else f"nuke.createNode('{node_type}')"
        return self.execute(code)

    def execute_file(self, filepath):
        """Execute a Python file inside Nuke."""
        with open(filepath, "r") as f:
            code = f.read()
        return self.execute(code)

    def get_all_nodes(self):
        """Return a list of all node names in the current Nuke script."""
        return self.execute("[n.name() for n in nuke.allNodes()]")

    def save_script(self, filepath=None):
        """Save the current Nuke script."""
        if filepath:
            return self.execute(f"nuke.scriptSaveAs('{filepath}')")
        return self.execute("nuke.scriptSave()")

    def _receive(self, buffer_size=65536):
        """Receive data from the socket."""
        chunks = []
        while True:
            try:
                chunk = self._socket.recv(buffer_size)
                if not chunk:
                    break
                chunks.append(chunk)
                if chunk.endswith(b"\n"):
                    break
            except socket.timeout:
                break
        return b"".join(chunks).decode("utf-8").strip()

    def close(self):
        """Close the connection."""
        if self._socket:
            try:
                payload = json.dumps({"type": "disconnect"})
                self._socket.sendall(payload.encode("utf-8") + b"\n")
            except Exception:
                pass
            self._socket.close()
            self._connected = False
            print("[NukeConnector] Disconnected from Nuke.")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __repr__(self):
        status = "connected" if self._connected else "disconnected"
        return f"NukeConnector({self.host}:{self.port}, {status})"
