"""
BubbleTalk OBS Script
=====================
Adds speech bubble overlays to your OBS scene via a Browser Source.
No extra Python packages required — uses only the standard library.

SETUP
-----
1. In OBS: Tools > Scripts > click "+" > select this file.
2. Add a Browser Source to your scene:
      URL    : http://127.0.0.1:42680/bubble_overlay.html
      Width  : 1920   Height : 1080   FPS : 30
      ✓ Shutdown source when not visible  → OFF
      ✓ Refresh browser when scene becomes active → OFF
      Custom CSS: (leave blank)
3. Open http://127.0.0.1:42680/control_panel.html in a browser tab to
   type messages and press Enter to send them.
"""

import obspython as obs
import json
import os
import threading
from datetime import datetime, timedelta
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 42680
DEFAULT_DURATION = 15

# ---------------------------------------------------------------------------
# Module-level state  (mutated only on the OBS main thread except where noted)
# ---------------------------------------------------------------------------
_script_dir: str = ""
_state_file: str = ""
_state_lock = threading.Lock()
_http_server: Optional[HTTPServer] = None

# Settings mirror (updated by script_update)
_current_text: str = ""
_duration: int = DEFAULT_DURATION
_bubble_x: int = 100
_bubble_y: int = 150
_font_size: int = 22
_bubble_scale: int = 100   # percent (50–200)


# ---------------------------------------------------------------------------
# HTTP server — serves the plugin directory so the browser source can
# fetch bubble_overlay.html and bubble_state.json over localhost.
# ---------------------------------------------------------------------------

class _SilentHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with logging suppressed, CORS headers, and POST API."""

    def log_message(self, *_args):
        pass  # keep OBS log clean

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        """API endpoints: POST /send  and  POST /clear"""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"

        if self.path == "/send":
            try:
                data = json.loads(body)
                text = str(data.get("text", "")).strip()
                if text:
                    _send_bubble(text)
                self._reply({"ok": True})
            except Exception as exc:
                self._reply({"ok": False, "error": str(exc)}, 400)

        elif self.path == "/clear":
            _clear_bubbles()
            self._reply({"ok": True})

        elif self.path == "/config":
            try:
                data = json.loads(body)
                _apply_config_from_post(data)
                self._reply({"ok": True})
            except Exception as exc:
                self._reply({"ok": False, "error": str(exc)}, 400)

        else:
            self.send_error(404)

    def _reply(self, data: dict, status: int = 200) -> None:
        encoded = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class _ReuseServer(HTTPServer):
    allow_reuse_address = True


def _start_server() -> None:
    global _http_server
    handler = partial(_SilentHandler, directory=_script_dir)
    try:
        _http_server = _ReuseServer(("127.0.0.1", PORT), handler)
        t = threading.Thread(target=_http_server.serve_forever, daemon=True)
        t.start()
        print(f"[BubbleTalk] HTTP server started → http://127.0.0.1:{PORT}")
    except OSError as exc:
        print(f"[BubbleTalk] Could not start HTTP server on port {PORT}: {exc}")
        print("[BubbleTalk] Is the script already loaded in another OBS instance?")


def _stop_server() -> None:
    global _http_server
    if _http_server:
        _http_server.shutdown()
        _http_server = None


# ---------------------------------------------------------------------------
# State file helpers
# ---------------------------------------------------------------------------

def _default_config() -> dict:
    return {
        "x": _bubble_x,
        "y": _bubble_y,
        "fontSize": _font_size,
        "scale": _bubble_scale / 100.0,
    }


def _write_state(messages: list, config: Optional[dict] = None) -> None:
    data = {"messages": messages, "config": config or _default_config()}
    with _state_lock:
        try:
            with open(_state_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception as exc:
            print(f"[BubbleTalk] State write error: {exc}")


def _read_state() -> dict:
    with _state_lock:
        try:
            if os.path.exists(_state_file):
                with open(_state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    return {"messages": [], "config": _default_config()}


def _purge_expired(messages: list) -> list:
    now = datetime.now()
    return [m for m in messages if datetime.fromisoformat(m["expires_at"]) > now]


# ---------------------------------------------------------------------------
# Bubble actions
# ---------------------------------------------------------------------------

def _send_bubble(text: str) -> None:
    if not text.strip():
        return
    state = _read_state()
    messages = _purge_expired(state.get("messages", []))
    expires_at = (datetime.now() + timedelta(seconds=_duration)).isoformat()
    messages.append({"text": text.strip(), "expires_at": expires_at})
    _write_state(messages, _default_config())


def _clear_bubbles() -> None:
    _write_state([], _default_config())


def _update_config_only() -> None:
    """Push current styling config to the state file without touching messages."""
    if not _state_file:
        return
    state = _read_state()
    messages = _purge_expired(state.get("messages", []))
    _write_state(messages, _default_config())


def _apply_config_from_post(data: dict) -> None:
    """Update styling variables from a POST /config request and persist to state."""
    global _bubble_x, _bubble_y, _font_size, _bubble_scale
    if "bubble_x" in data:
        _bubble_x = max(0, min(1880, int(data["bubble_x"])))
    if "bubble_y" in data:
        _bubble_y = max(0, min(1040, int(data["bubble_y"])))
    if "font_size" in data:
        _font_size = max(12, min(72, int(data["font_size"])))
    if "bubble_scale" in data:
        _bubble_scale = max(50, min(200, int(data["bubble_scale"])))
    _update_config_only()


# ---------------------------------------------------------------------------
# OBS button callbacks
# ---------------------------------------------------------------------------

def _on_send(props, prop):
    _send_bubble(_current_text)
    return True


def _on_clear(props, prop):
    _clear_bubbles()
    return True


# ---------------------------------------------------------------------------
# OBS Script API
# ---------------------------------------------------------------------------

def script_description() -> str:
    return (
        "<b>BubbleTalk</b> — speech bubble overlay for OBS<br><br>"
        "<b>1. Browser Source</b> (add to your scene):<br>"
        f"&nbsp;&nbsp;URL: <tt>http://127.0.0.1:{PORT}/bubble_overlay.html</tt><br>"
        "&nbsp;&nbsp;Width: <b>1920</b> &nbsp; Height: <b>1080</b> &nbsp; FPS: 30<br>"
        "&nbsp;&nbsp;Uncheck <i>Local file</i> — leave Custom CSS blank<br><br>"
        "<b>2. Control panel</b> (open in any browser tab):<br>"
        f"&nbsp;&nbsp;<tt>http://127.0.0.1:{PORT}/control_panel.html</tt><br>"
        "&nbsp;&nbsp;Type a message and press <b>Enter</b> to send."
    )


def script_load(settings) -> None:
    global _script_dir, _state_file
    _script_dir = os.path.dirname(os.path.realpath(__file__))
    _state_file = os.path.join(_script_dir, "bubble_state.json")
    _write_state([])
    _start_server()


def script_unload() -> None:
    _stop_server()
    _write_state([])


def script_defaults(settings) -> None:
    obs.obs_data_set_default_int(settings, "duration", DEFAULT_DURATION)


def script_update(settings) -> None:
    global _current_text, _duration
    _current_text = obs.obs_data_get_string(settings, "message_text")
    _duration     = obs.obs_data_get_int(settings, "duration") or DEFAULT_DURATION


def script_properties():
    props = obs.obs_properties_create()

    # --- Message ---
    obs.obs_properties_add_text(
        props, "message_text", "Message", obs.OBS_TEXT_DEFAULT
    )
    obs.obs_properties_add_button(props, "send_btn", "  Send  ", _on_send)
    obs.obs_properties_add_int(
        props, "duration", "Display Duration (seconds)", 3, 60, 1
    )
    obs.obs_properties_add_button(props, "clear_btn", "Clear All Bubbles", _on_clear)

    # Position and styling are controlled via the control panel.

    return props
