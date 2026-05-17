#!/usr/bin/env python3
"""
launch_blob_viewer.py — 一键启动 LLM Invocation Archive Viewer

从 .env.local.L4 读取 SPN credentials，获取 Azure Storage Bearer token，
注入到 blob-viewer.html，然后启动本地 HTTP 服务器（http://localhost:8888）。

用法：
    python3 apps/launch_blob_viewer.py
    # 浏览器会自动打开 http://localhost:8888

依赖：
    Python 标准库即可，不需要 azure-identity
"""

import http.server
import json
import os
import re
import socketserver  # for ThreadingMixIn
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib import request as urllib_request
from urllib.parse import parse_qs, quote, urlencode, urlparse

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE   = _REPO_ROOT / ".env.local.L4"
_HTML_FILE  = Path(__file__).resolve().parent / "blob-viewer.html"
_PORT       = int(os.getenv("BLOB_VIEWER_PORT", "8888"))

_STORAGE_ACCOUNT = "aigoverntrustworthysa"
_CONTAINER        = "ai-invocation-archive"
_PREFIX           = "aigoverntrustworthy"
_SCOPE            = "https://storage.azure.com/.default"


def load_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        env[k.strip()] = v
    return env


def get_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    """Client credentials flow — no third-party library needed."""
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    body = urlencode({
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         _SCOPE,
    }).encode()
    req = urllib_request.Request(url, data=body,
                                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib_request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["access_token"]


def _storage_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "x-ms-version": "2020-04-08",
    }


def _blob_list(token: str, prefix: str, marker: str) -> dict[str, object]:
    query = {
        "restype": "container",
        "comp": "list",
        "maxresults": "500",
    }
    if prefix:
        query["prefix"] = prefix
    if marker:
        query["marker"] = marker

    url = (
        f"https://{_STORAGE_ACCOUNT}.blob.core.windows.net/{_CONTAINER}"
        f"?{urlencode(query)}"
    )
    req = urllib_request.Request(url, headers=_storage_headers(token))
    with urllib_request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8")

    names = [match.group(1) for match in re.finditer(r"<Name>(.*?)</Name>", text)]
    next_marker_match = re.search(r"<NextMarker>(.*?)</NextMarker>", text)
    next_marker = next_marker_match.group(1) if next_marker_match else ""
    return {"names": names, "next": next_marker}


def _blob_get(token: str, path: str) -> bytes:
    safe_path = quote(path.lstrip("/"), safe="/")
    url = f"https://{_STORAGE_ACCOUNT}.blob.core.windows.net/{_CONTAINER}/{safe_path}"
    req = urllib_request.Request(url, headers=_storage_headers(token))
    with urllib_request.urlopen(req, timeout=30) as resp:
        return resp.read()


def build_injected_html() -> bytes:
    """注入 auto-connect JS 到 blob-viewer.html，并通过本地代理访问 Blob。"""
    html = _HTML_FILE.read_text(encoding="utf-8")

    # 在 </head> 前注入一段 JS：页面加载后自动填入配置并连接
    inject = f"""
<script>
// Auto-injected by launch_blob_viewer.py — DO NOT COMMIT
window._autoConnect = {{
  acct:      "https://{_STORAGE_ACCOUNT}.blob.core.windows.net",
  container: "{_CONTAINER}",
  prefix:    "{_PREFIX}"
}};
window.addEventListener('load', function() {{
  var cfg = window._autoConnect;
  document.getElementById('acct-url').value   = cfg.acct;
  document.getElementById('container').value  = cfg.container;
  document.getElementById('sas-input').value  = 'local-proxy';
  document.getElementById('prefix-input').value = cfg.prefix;
  var label = document.querySelector('.sas-setup label:nth-of-type(3)');
  if (label) label.textContent = 'Connection Mode (local proxy)';
  connect();
}});
</script>
"""
    html = html.replace("</head>", inject + "</head>", 1)

    old_get = '''async function blobGet(path) {
  const url = `${CFG.acct}/${CFG.container}/${path}?${CFG.sas}`;
  const r = await fetch(url, { headers: { 'x-ms-version': '2020-04-08' } });'''
    new_get = '''async function blobGet(path) {
  const r = await fetch(`/api/blob?path=${encodeURIComponent(path)}`);'''
    html = html.replace(old_get, new_get, 1)

    old_list = '''async function blobList(prefix, marker='') {
  let url = `${CFG.acct}/${CFG.container}?restype=container&comp=list&maxresults=500&${CFG.sas}`;
  if (prefix) url += `&prefix=${encodeURIComponent(prefix)}`;
  if (marker) url += `&marker=${encodeURIComponent(marker)}`;
  const r = await fetch(url, { headers: { 'x-ms-version': '2020-04-08' } });
  if (!r.ok) throw new Error(`List failed HTTP ${r.status}`);
  const text = await r.text();
  const names = [...text.matchAll(/<Name>(.*?)<\\/Name>/g)].map(m => m[1]);
  const next  = (text.match(/<NextMarker>(.*?)<\\/NextMarker>/) || [])[1] || '';
  return { names, next };
}'''
    new_list = '''async function blobList(prefix, marker='') {
  const params = new URLSearchParams();
  if (prefix) params.set('prefix', prefix);
  if (marker) params.set('marker', marker);
  const r = await fetch(`/api/list?${params.toString()}`);
  if (!r.ok) throw new Error(`List failed HTTP ${r.status}`);
  return r.json();
}'''
    html = html.replace(old_list, new_list, 1)

    return html.encode("utf-8")


class Handler(http.server.BaseHTTPRequestHandler):
    injected_html: bytes = b""
    token: str = ""
    token_expires_at: float = 0.0
    _creds: tuple = ()  # (tenant_id, client_id, client_secret)
    _lock = __import__("threading").Lock()

    def _send_no_cache_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    @classmethod
    def _get_fresh_token(cls) -> str:
        """Return a valid token, refreshing if within 5 minutes of expiry."""
        import time
        with cls._lock:
            if time.time() >= cls.token_expires_at - 300 and cls._creds:
                cls.token = get_token(*cls._creds)
                cls.token_expires_at = time.time() + 3600
        return cls.token

    def do_GET(self):
        if self.path in ("/", "/blob-viewer.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._send_no_cache_headers()
            self.send_header("Content-Length", str(len(self.injected_html)))
            self.end_headers()
            self.wfile.write(self.injected_html)
        elif self.path.startswith("/api/list"):
            params = parse_qs(urlparse(self.path).query)
            try:
                payload = json.dumps(
                    _blob_list(
                        self._get_fresh_token(),
                        params.get("prefix", [""])[0],
                        params.get("marker", [""])[0],
                    )
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._send_no_cache_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as exc:
                payload = json.dumps({"error": str(exc)}).encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._send_no_cache_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        elif self.path.startswith("/api/blob"):
            params = parse_qs(urlparse(self.path).query)
            blob_path = params.get("path", [""])[0]
            if not blob_path:
                self.send_response(400)
                self.end_headers()
                return
            try:
                payload = _blob_get(self._get_fresh_token(), blob_path)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._send_no_cache_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as exc:
                payload = json.dumps({"error": str(exc)}).encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self._send_no_cache_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # suppress server log noise


def main():
    print("=" * 55)
    print("  LLM Invocation Archive Viewer — Launcher")
    print("=" * 55)

    env = load_env(_ENV_FILE)
    tenant_id     = env.get("AZURE_TENANT_ID", "")
    client_id     = env.get("L4_RAG_SERVICE_CLIENT_ID", "")
    client_secret = env.get("L4_RAG_SERVICE_CLIENT_SECRET", "")

    if not all([tenant_id, client_id, client_secret]):
        print("[ERROR] Missing SPN credentials in .env.local.L4:")
        print("        AZURE_TENANT_ID, L4_RAG_SERVICE_CLIENT_ID, L4_RAG_SERVICE_CLIENT_SECRET")
        sys.exit(1)

    print(f"  SPN client_id : {client_id}")
    print(f"  Tenant        : {tenant_id}")
    print(f"  Storage       : {_STORAGE_ACCOUNT}/{_CONTAINER}")
    print()
    print("[1/3] 获取 Azure Storage Bearer token...")
    try:
        token = get_token(tenant_id, client_id, client_secret)
        print(f"      Token 获取成功 ({len(token)} chars)")
    except Exception as e:
        print(f"[ERROR] 获取 token 失败: {e}")
        sys.exit(1)

    print("[2/3] 注入本地代理配置到 HTML...")
    Handler.token = token
    Handler._creds = (tenant_id, client_id, client_secret)
    import time
    Handler.token_expires_at = time.time() + 3600
    Handler.injected_html = build_injected_html()
    print(f"      HTML 大小: {len(Handler.injected_html):,} bytes")

    print(f"[3/3] 启动本地服务器 http://localhost:{_PORT} ...")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", _PORT), Handler)

    def open_browser():
        time.sleep(0.8)
        webbrowser.open(f"http://localhost:{_PORT}/")

    threading.Thread(target=open_browser, daemon=True).start()

    print()
    print(f"  ✅ 打开浏览器访问: http://localhost:{_PORT}/")
    print("  Ctrl+C 停止服务器")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[停止] 服务器已关闭")


if __name__ == "__main__":
    main()
