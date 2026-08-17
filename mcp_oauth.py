"""MCP OAuth 2.1 (DCR + PKCE) — claude.ai 커스텀 커넥터 직접 연결용.

기존 무인증 경로 /mcphttp/mcp 는 그대로 두고,
인증이 필요한 /mcpauth/mcp 를 별도로 제공한다.

상태 저장 없음: 모든 토큰은 HMAC 서명 방식(자체 검증)이라 DB·메모리 불필요.
(stock-final의 검증된 mcp_oauth.py를 etf-analyzer용으로 이식)
"""
import os
import time
import json
import hmac
import base64
import hashlib
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse

BASE = os.environ.get("MCP_PUBLIC_BASE", "https://etf-analyzer.replit.app").rstrip("/")
RESOURCE = f"{BASE}/mcpauth/mcp"
SECRET = os.environ.get("MCP_OAUTH_SECRET", "budcode-etf-mcp-oauth-v1-2026").encode()

ACCESS_TTL = 60 * 60 * 24 * 30      # 30일
REFRESH_TTL = 60 * 60 * 24 * 365    # 1년
CODE_TTL = 300                      # 5분


# ─────────────────────────────────────────────
# 서명 토큰 (JWT 유사, 의존성 없음)
# ─────────────────────────────────────────────
def _b64(raw: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def _sign(payload: dict, ttl: int) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl
    raw = _b64(json.dumps(body, separators=(",", ":")).encode())
    sig = _b64(hmac.new(SECRET, raw, hashlib.sha256).digest())
    return (raw + b"." + sig).decode()


def verify(token: str):
    """유효하면 payload dict, 아니면 None"""
    try:
        raw, sig = token.encode().split(b".", 1)
        expect = _b64(hmac.new(SECRET, raw, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expect):
            return None
        data = json.loads(base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4)))
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return data
    except Exception:
        return None


# ─────────────────────────────────────────────
# 메타데이터 (RFC 9728 / RFC 8414)
# ─────────────────────────────────────────────
router = APIRouter()

_PRM = {
    "resource": RESOURCE,
    "authorization_servers": [BASE],
    "scopes_supported": ["mcp"],
    "bearer_methods_supported": ["header"],
}

_ASM = {
    "issuer": BASE,
    "authorization_endpoint": f"{BASE}/oauth/authorize",
    "token_endpoint": f"{BASE}/oauth/token",
    "registration_endpoint": f"{BASE}/oauth/register",
    "scopes_supported": ["mcp", "offline_access"],
    "response_types_supported": ["code"],
    "grant_types_supported": ["authorization_code", "refresh_token"],
    "code_challenge_methods_supported": ["S256"],
    "token_endpoint_auth_methods_supported": ["none"],
}


@router.get("/.well-known/oauth-protected-resource")
def prm_root():
    return JSONResponse(_PRM)


@router.get("/.well-known/oauth-protected-resource/{tail:path}")
def prm_path(tail: str):
    return JSONResponse(_PRM)


@router.get("/.well-known/oauth-authorization-server")
def asm_root():
    return JSONResponse(_ASM)


@router.get("/.well-known/oauth-authorization-server/{tail:path}")
def asm_path(tail: str):
    return JSONResponse(_ASM)


# ─────────────────────────────────────────────
# Dynamic Client Registration (RFC 7591)
# ─────────────────────────────────────────────
@router.post("/oauth/register")
async def register(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    return JSONResponse(
        {
            "client_id": "budcode-etf-" + secrets.token_urlsafe(16),
            "client_id_issued_at": int(time.time()),
            "client_name": body.get("client_name", "MCP Client"),
            "redirect_uris": body.get("redirect_uris", []),
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
        status_code=201,
    )


# ─────────────────────────────────────────────
# Authorization (동의 화면 → code 발급)
# ─────────────────────────────────────────────
_CONSENT = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>부코드AI ETF 분석기 연결</title><style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#F6F7F9;color:#171B26;
font-family:"Pretendard Variable",Pretendard,-apple-system,"Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif}
.card{background:#fff;border:1px solid #E2E6EC;border-radius:14px;padding:34px 30px;max-width:400px;width:calc(100% - 32px);
box-shadow:0 1px 3px rgba(20,30,50,.06)}
h1{margin:0 0 6px;font-size:20px;font-weight:800;letter-spacing:-.01em}
p{margin:0;color:#656E82;font-size:14.5px;line-height:1.65}
ul{margin:18px 0 0;padding-left:18px;color:#171B26;font-size:14.5px;line-height:1.8}
button{margin-top:24px;width:100%;padding:13px;border:0;border-radius:9px;background:#0F6E64;color:#fff;
font:inherit;font-size:15px;font-weight:700;cursor:pointer}
button:hover{background:#0C5C54}
.sub{margin-top:12px;font-size:12.5px;color:#8A93A5;text-align:center}
@media(prefers-color-scheme:dark){body{background:#101319;color:#E8EBF0}
.card{background:#171B23;border-color:#262C38;box-shadow:none}p{color:#9AA3B5}ul{color:#E8EBF0}
button{background:#2DD4BF;color:#04211E}button:hover{background:#25B8A6}.sub{color:#767F91}}
</style></head><body><div class="card">
<h1>부코드AI ETF 분석기</h1>
<p>Claude에서 이 도구를 사용할 수 있도록 연결합니다.</p>
<ul><li>한국·미국 ETF 검색과 상세 정보</li><li>여러 ETF 비교 분석</li><li>포트폴리오 추천</li></ul>
<form method="post" action="/oauth/approve">%FIELDS%
<button type="submit">연결 허용</button></form>
<div class="sub">읽기 전용입니다. 계정 정보는 요구하지 않습니다.</div>
</div></body></html>"""


def _esc(v: str) -> str:
    return (str(v or "")
            .replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


@router.get("/oauth/authorize")
def authorize(
    client_id: str = "",
    redirect_uri: str = "",
    state: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "S256",
    scope: str = "mcp",
    response_type: str = "code",
    resource: str = "",
):
    if not redirect_uri:
        return JSONResponse({"error": "invalid_request",
                             "error_description": "redirect_uri required"}, status_code=400)
    fields = "".join(
        f'<input type="hidden" name="{k}" value="{_esc(v)}">'
        for k, v in (
            ("client_id", client_id),
            ("redirect_uri", redirect_uri),
            ("state", state),
            ("code_challenge", code_challenge),
            ("code_challenge_method", code_challenge_method),
            ("scope", scope),
        )
    )
    return HTMLResponse(_CONSENT.replace("%FIELDS%", fields))


@router.post("/oauth/approve")
def approve(
    client_id: str = Form(""),
    redirect_uri: str = Form(...),
    state: str = Form(""),
    code_challenge: str = Form(""),
    code_challenge_method: str = Form("S256"),
    scope: str = Form("mcp"),
):
    code = _sign(
        {"typ": "code", "cid": client_id, "cc": code_challenge,
         "ccm": code_challenge_method, "ru": redirect_uri, "scp": scope},
        CODE_TTL,
    )
    q = {"code": code}
    if state:
        q["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}{urlencode(q)}", status_code=302)


# ─────────────────────────────────────────────
# Token (authorization_code / refresh_token)
# ─────────────────────────────────────────────
def _issue(scope: str = "mcp"):
    return JSONResponse({
        "access_token": _sign({"typ": "access", "sub": "budcode-etf", "scp": scope}, ACCESS_TTL),
        "token_type": "Bearer",
        "expires_in": ACCESS_TTL,
        "refresh_token": _sign({"typ": "refresh", "sub": "budcode-etf", "scp": scope}, REFRESH_TTL),
        "scope": scope,
    })


@router.post("/oauth/token")
async def token(request: Request):
    form = await request.form()
    grant = form.get("grant_type", "")

    if grant == "authorization_code":
        data = verify(form.get("code", ""))
        if not data or data.get("typ") != "code":
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        challenge = data.get("cc") or ""
        if challenge:
            verifier = form.get("code_verifier", "") or ""
            if data.get("ccm", "S256") == "plain":
                calc = verifier
            else:
                calc = _b64(hashlib.sha256(verifier.encode()).digest()).decode()
            if not hmac.compare_digest(calc, challenge):
                return JSONResponse({"error": "invalid_grant",
                                     "error_description": "PKCE verification failed"}, status_code=400)
        return _issue(data.get("scp", "mcp"))

    if grant == "refresh_token":
        data = verify(form.get("refresh_token", ""))
        if not data or data.get("typ") != "refresh":
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        return _issue(data.get("scp", "mcp"))

    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)


# ─────────────────────────────────────────────
# Bearer 게이트 (ASGI 미들웨어)
# ─────────────────────────────────────────────
class BearerGate:
    """감싼 ASGI 앱을 Bearer 토큰으로 보호. 미인증 시 401 + WWW-Authenticate."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        auth = ""
        for k, v in scope.get("headers") or []:
            if k == b"authorization":
                auth = v.decode("latin-1")
                break
        tok = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
        if not verify(tok):
            body = json.dumps({"error": "invalid_token",
                               "error_description": "Authorization required"}).encode()
            hdr = f'Bearer resource_metadata="{BASE}/.well-known/oauth-protected-resource"'
            await send({"type": "http.response.start", "status": 401, "headers": [
                (b"content-type", b"application/json"),
                (b"www-authenticate", hdr.encode()),
                (b"content-length", str(len(body)).encode()),
            ]})
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)
