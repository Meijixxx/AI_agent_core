"""Web 取得ツール: 公開 URL から HTML/テキストを取得"""

import ipaddress
import re
import socket
import urllib.parse
import urllib.request

TIMEOUT = 10
MAX_CHARS = 5000
USER_AGENT = "AI-Agent-Core/1.0"


def _is_private_host(host: str) -> bool:
    """localhost や内部 IP を拒否する（簡易 SSRF 対策）。"""
    if not host:
        return True
    host_lower = host.lower()
    if host_lower in ("localhost", "localhost.localdomain"):
        return True
    try:
        ip_list = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False  # 名前解決失敗 → urlopen 側でエラーに任せる

    for family, _, _, _, sockaddr in ip_list:
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False


def _strip_html(text: str) -> str:
    """HTML タグを除去し、連続空白を圧縮する。"""
    # script / style 内容を削除
    text = re.sub(r"<script\b[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style\b[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # タグ除去
    text = re.sub(r"<[^>]+>", "", text)
    # HTML エンティティ（基本）
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    # 空白圧縮
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def fetch_url(url: str) -> str:
    """公開 URL の内容を取得する。HTML は簡易テキスト化、長さ制限あり。"""
    if not url or not isinstance(url, str):
        return "[エラー] url を指定してください"

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"[エラー] http/https 以外のスキーマは使用できません: {parsed.scheme}"

    if _is_private_host(parsed.hostname or ""):
        return f"[拒否] 内部アドレスへのアクセスは許可されていません: {parsed.hostname}"

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            raw = resp.read(1024 * 1024)  # 最大 1MB 読み込み
    except urllib.error.HTTPError as e:
        return f"[エラー] HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"[エラー] URL アクセス失敗: {e.reason}"
    except socket.timeout:
        return f"[タイムアウト] {TIMEOUT}秒 で応答がありませんでした"
    except Exception as e:
        return f"[エラー] 取得に失敗: {e}"

    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception as e:
        return f"[エラー] デコード失敗: {e}"

    if "html" in content_type or "<html" in text[:500].lower():
        text = _strip_html(text)

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n... ({len(text) - MAX_CHARS}文字省略)"

    return text or "(本文なし)"
