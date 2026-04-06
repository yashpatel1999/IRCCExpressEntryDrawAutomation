import json
import os
import subprocess
import queue
import threading


DEFAULT_MCP_COMMAND = ["node", "mcp/playwright_server.mjs"]
DEFAULT_TOOL_NAME = "capture_draw_rows"


class McpError(RuntimeError):
    pass


class McpJsonRpcClient(object):
    def __init__(self, command=None, cwd=None, request_timeout_seconds=None):
        self.command = command or DEFAULT_MCP_COMMAND
        self.cwd = cwd
        self.request_timeout_seconds = request_timeout_seconds or int(os.environ.get("IRCC_MCP_REQUEST_TIMEOUT_SECONDS", "120"))
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._next_id = 1
        self._messages = queue.Queue()
        self._reader_error = None
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def close(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(5)
            except Exception:
                self.process.kill()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1)

    def request(self, method, params=None):
        request_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        self._send(payload)
        while True:
            try:
                message = self._messages.get(timeout=self.request_timeout_seconds)
            except queue.Empty:
                raise McpError("Timed out waiting for MCP response from %s." % " ".join(self.command))
            if message is None:
                if self._reader_error:
                    raise McpError(self._reader_error)
                raise McpError("MCP reader stopped unexpectedly.")
            if message.get("id") == request_id:
                return message

    def notify(self, method, params=None):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        self._send(payload)

    def _send(self, payload):
        body = json.dumps(payload).encode("utf-8")
        header = "Content-Length: %d\r\n\r\n" % len(body)
        self.process.stdin.write(header.encode("utf-8"))
        self.process.stdin.write(body)
        self.process.stdin.flush()

    def _reader_loop(self):
        try:
            while True:
                message = self._read_message()
                self._messages.put(message)
        except Exception as exc:
            self._reader_error = str(exc)
            self._messages.put(None)

    def _read_message(self):
        headers = {}
        while True:
            line = self.process.stdout.readline()
            if not line:
                stderr = self.process.stderr.read()
                raise McpError("MCP process exited unexpectedly: %s" % stderr.decode("utf-8", "ignore"))
            if line in (b"\r\n", b"\n"):
                break
            decoded = line.decode("utf-8", "ignore").strip()
            if ":" in decoded:
                key, value = decoded.split(":", 1)
                headers[key.lower()] = value.strip()

        content_length = int(headers.get("content-length", "0"))
        if not content_length:
            raise McpError("Missing Content-Length from MCP response.")
        body = self.process.stdout.read(content_length)
        if not body:
            raise McpError("Empty MCP response body.")
        return json.loads(body.decode("utf-8"))


def capture_draw_rows_via_mcp(url, command=None):
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    client = McpJsonRpcClient(command=command, cwd=repo_root)
    try:
        client.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "ircc-draw-automation", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            },
        )
        client.notify("initialized", {})
        response = client.request(
            "tools/call",
            {
                "name": DEFAULT_TOOL_NAME,
                "arguments": {"url": url},
            },
        )
        if "error" in response:
            raise McpError(response["error"].get("message", "MCP tool call failed"))
        content = response.get("result", {}).get("content", [])
        if not content:
            raise McpError("MCP tool response did not include content.")
        text = content[0].get("text", "")
        return json.loads(text)
    finally:
        client.close()
