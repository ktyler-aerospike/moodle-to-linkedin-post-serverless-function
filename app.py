# app.py
import os
import json
import time
import hmac
import hashlib
import secrets
from urllib.parse import urlencode
import requests
from flask import Flask, redirect, request, jsonify, make_response, abort
from werkzeug.middleware.proxy_fix import ProxyFix
from itsdangerous import TimestampSigner, BadSignature, SignatureExpired
from dotenv import load_dotenv

load_dotenv(override=True)

# ----- Environment -----
CLIENT_ID      = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET  = os.getenv("LINKEDIN_CLIENT_SECRET")
# We will compute redirect_uri dynamically; keep env around if you prefer static in prod
REDIRECT_URI_ENV = os.getenv("LINKEDIN_REDIRECT_URI")
PORT           = int(os.getenv("PORT", "8080"))

ENV            = os.getenv("ENV", "dev")   # "dev" on localhost, "prod" in production
COOKIE_DOMAIN  = os.getenv("COOKIE_DOMAIN") # e.g., "api.example.com" (omit for localhost)

STATE_SECRET   = os.getenv("STATE_SIGNING_SECRET", "dev-override-me")
STATE_TTL_SECS = int(os.getenv("STATE_TTL_SECS", "600"))  # 10 min default
STATE_COOKIE   = os.getenv("STATE_COOKIE_NAME", "li_state")

# ----- Scopes/Endpoints -----
SCOPES = ["openid", "profile", "w_member_social"]

AUTH_URL       = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL      = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL   = "https://api.linkedin.com/v2/userinfo"
UGC_POSTS_URL  = "https://api.linkedin.com/v2/ugcPosts"

POSTS_URL          = "https://api.linkedin.com/rest/posts"
IMAGES_INIT_URL    = "https://api.linkedin.com/rest/images?action=initializeUpload"
ASSETS_REGISTER_URL= "https://api.linkedin.com/v2/assets?action=registerUpload"

BADGE_IMG_STUB       = "https://catalog.learn.aerospike.com/img/badges/"
BADGE_DETAILS_STUB    = "https://catalog.learn.aerospike.com/"
VERIFICATION_STUB     = "https://learn.aerospike.com/admin/tool/certificate/index.php?code="
ALLOWED_START_PARAMS  = ("badgeid", "verifcode")

TOKENS = {}  # user_key -> { access_token, expires_at, refresh_token?, person_urn }

# ----- App setup -----
def _now() -> int:
    return int(time.time())

app = Flask(__name__)
# Trust proxy headers so we see the public scheme/host behind a gateway
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1)

signer = TimestampSigner(STATE_SECRET)

# ----- Helpers -----
def mask(s: str):
    if not s:
        return None
    return s if len(s) < 6 else s[:3] + "…" + s[-3:]

def _ua_hash() -> str:
    return hashlib.sha256((request.headers.get("User-Agent") or "").encode()).hexdigest()

def _sign_state(payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":")).encode()
    return signer.sign(body).decode()

def _unsign_state(token: str) -> dict:
    body = signer.unsign(token, max_age=STATE_TTL_SECS)
    return json.loads(body.decode())

def build_redirect_uri() -> str:
    """
    Always compute redirect_uri from the current request's public host/proto.
    Prevents 'mixed host' issues between localhost and gateway.
    """
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
    host   = request.headers.get("X-Forwarded-Host", request.host)
    return f"{scheme}://{host}/auth/linkedin/callback"

def set_state_cookie(response, value: str, max_age: int):
    """
    Dev (localhost): cookie works over http with SameSite=Lax, Secure=False.
    Prod (https): SameSite=None; Secure=True.
    """
    is_local = ("localhost" in request.host) or (ENV.lower() == "dev")
    kwargs = dict(
        key=STATE_COOKIE,
        value=value,
        max_age=max_age,
        httponly=True,
        path="/",
        samesite="Lax" if is_local else "None",
        secure=False if is_local else True,
    )
    if COOKIE_DOMAIN and not is_local:
        kwargs["domain"] = COOKIE_DOMAIN
    response.set_cookie(**kwargs)

def clear_state_cookie(response):
    is_local = ("localhost" in request.host) or (ENV.lower() == "dev")
    kwargs = dict(
        key=STATE_COOKIE,
        value="",
        max_age=0,
        httponly=True,
        path="/",
        samesite="Lax" if is_local else "None",
        secure=False if is_local else True,
    )
    if COOKIE_DOMAIN and not is_local:
        kwargs["domain"] = COOKIE_DOMAIN
    response.set_cookie(**kwargs)

def exchange_code_for_tokens_with_redirect(code: str, redirect_uri: str) -> dict:
    """Exchange the authorization code for tokens using the exact same redirect_uri."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    r = requests.post(TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    print("TOKEN RESP:", r.status_code, r.text[:200], "...")
    r.raise_for_status()
    tok = r.json()
    return {
        "access_token": tok["access_token"],
        "expires_at": _now() + int(tok.get("expires_in", 0)),
        "refresh_token": tok.get("refresh_token"),
        "refresh_token_expires_in": tok.get("refresh_token_expires_in"),
    }

def get_auth_header(user_key: str):
    rec = TOKENS.get(user_key)
    if not rec:
        return None
    return {"Authorization": f"Bearer {rec['access_token']}"}

def current_user_key():
    # Replace with your Moodle user id mapping. For demo we use remote_addr.
    return request.remote_addr or "demo-user"

# ----- Image/Post helpers -----
def init_rest_image_upload(owner_urn: str, headers: dict) -> tuple[str, str]:
    payload = {"initializeUploadRequest": {"owner": owner_urn}}
    r = requests.post(IMAGES_INIT_URL, headers=headers, json=payload)
    print("REST initializeUpload:", r.status_code, r.text[:300], "...")
    r.raise_for_status()
    data = r.json().get("value") or r.json()
    upload_url = data.get("uploadUrl") or (data.get("uploadUrlExpiresAt", {}) or {}).get("uploadUrl")
    image_urn = data.get("image") if isinstance(data.get("image"), str) else (data.get("image", {}) or {}).get("urn")
    if not upload_url or not image_urn:
        raise RuntimeError(f"Unexpected initializeUpload response: {r.text[:300]}")
    return upload_url, image_urn

def put_bytes_to_linkedin(upload_url: str, content_bytes: bytes, content_type: str = "image/png"):
    r = requests.put(upload_url, data=content_bytes, headers={"Content-Type": content_type})
    print("PUT upload:", r.status_code, r.text[:150], "...")
    r.raise_for_status()

def create_article_post(author_urn: str, thumbnail_urn: str, source_url: str, title: str, description: str, commentary: str, headers: dict):
    body = {
        "author": author_urn,
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "content": {
            "article": {
                "source": source_url,
                "thumbnail": thumbnail_urn,
                "title": title,
                "description": description
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }
    r = requests.post(POSTS_URL, headers=headers, json=body)
    print("POSTS API RESP:", r.status_code, r.text[:400], "...")
    return r

def init_v2_asset_upload(owner_urn: str, bearer_headers: dict) -> tuple[str, str]:
    payload = {
        "registerUploadRequest": {
            "owner": owner_urn,
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "serviceRelationships": [
                {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
            ]
        }
    }
    v2_headers = {**bearer_headers, "Content-Type": "application/json"}
    r = requests.post(ASSETS_REGISTER_URL, headers=v2_headers, json=payload)
    print("v2 assets registerUpload:", r.status_code, r.text[:300], "...")
    r.raise_for_status()
    j = r.json()["value"]
    upload_url = j["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset_urn = j["asset"]
    return upload_url, asset_urn

# ----- Routes -----
@app.route("/")
def home():
    return "Hello from Kristl's Cloud Run serverless function! Try /diag for diagnostic info, use /auth/linkedin/start to trigger the posting flow"

@app.route("/diag")
def diag():
    return {
        "env": ENV,
        "cookie_domain": COOKIE_DOMAIN,
        "LINKEDIN_CLIENT_ID": mask(CLIENT_ID),
        "LINKEDIN_REDIRECT_URI_env": REDIRECT_URI_ENV,
        "has_client_secret": bool(CLIENT_SECRET),
        "port": PORT,
        "scopes": " ".join(SCOPES),
        "state_cookie": STATE_COOKIE,
        "state_ttl_secs": STATE_TTL_SECS,
    }, 200

@app.route("/auth/linkedin/start")
def linkedin_start():
    if not all([CLIENT_ID, CLIENT_SECRET]):
        return "Missing envs: LINKEDIN_CLIENT_ID/SECRET", 500

    # Allowlist query params and carry through (inside signed state)
    incoming = {k: v for k, v in request.args.items() if k in ALLOWED_START_PARAMS}

    payload = {
        "jti": secrets.token_hex(16),
        "ua": _ua_hash(),
        "params": incoming,
    }
    state_token = _sign_state(payload)

    redirect_uri = build_redirect_uri()  # dynamic for current host
    query = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
        "state": state_token,
        "scope": " ".join(SCOPES),
    }
    auth_url = f"{AUTH_URL}?{urlencode(query)}"
    print("AUTH URL:", auth_url)

    resp = make_response(redirect(auth_url, code=302))
    set_state_cookie(resp, state_token, STATE_TTL_SECS)
    return resp

@app.route("/auth/linkedin/callback")
def linkedin_callback():
    # LinkedIn error?
    if request.args.get("error"):
        return {
            "error": request.args.get("error"),
            "error_description": request.args.get("error_description"),
        }, 400

    # Cookie ↔ query state comparison
    state_qs = request.args.get("state") or ""
    state_ck = request.cookies.get(STATE_COOKIE) or ""
    if not state_qs or not state_ck or not hmac.compare_digest(state_qs, state_ck):
        # Temporary diagnostics (remove after you’re confident)
        print("DEBUG state mismatch:", {
            "have_qs": bool(state_qs),
            "have_cookie": bool(state_ck),
            "host": request.host,
            "xf_host": request.headers.get("X-Forwarded-Host"),
            "xf_proto": request.headers.get("X-Forwarded-Proto"),
            "path": request.full_path
        })
        return "State mismatch. Possible CSRF (cookie vs query).", 400

    # Verify signature/TTL and UA binding
    try:
        payload = _unsign_state(state_qs)
    except SignatureExpired:
        return "State expired.", 400
    except BadSignature:
        return "Invalid state signature.", 400

    if payload.get("ua") != _ua_hash():
        return "State UA mismatch. Possible CSRF.", 400

    code = request.args.get("code")
    if not code:
        return "Missing authorization code.", 400

    # Invalidate cookie (single-use)
    resp = make_response()

    clear_state_cookie(resp)

    # Use the same redirect_uri string for the token exchange
    redirect_uri = build_redirect_uri()
    tokens = exchange_code_for_tokens_with_redirect(code=code, redirect_uri=redirect_uri)

    # Get userinfo → person URN
    ui = requests.get(USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"})
    print("USERINFO RESP:", ui.status_code, ui.text[:200], "...")
    ui.raise_for_status()
    userinfo = ui.json()
    person_urn = f"urn:li:person:{userinfo['sub']}"

    # Persist tokens for your app user
    ukey = current_user_key()
    TOKENS[ukey] = {
        **tokens,
        "person_urn": person_urn,
        "userinfo": userinfo,
    }

    # Rehydrate allowed params carried in signed state
    params = payload.get("params", {}) or {}

    def hidden_inputs(d):
        return "".join(
            f'<input type="hidden" name="{k}" value="{(d.get(k) or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")}"/>'
            for k in ALLOWED_START_PARAMS if k in d
        )

    html = f"""
    <html>
        <head><title>LinkedIn Connected</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 40px;">
            <h2>✅ LinkedIn Connected.</h2>
            <p>You can now post your badge announcement to LinkedIn.</p>
            <form action="/post-image" method="post">
            {hidden_inputs(params)}
                <button type="submit" 
                        style="padding: 10px 20px; 
                               font-size: 16px; 
                               cursor: pointer;">
                    Post My Badge Announcement
                </button>
            </form>
        </body>
    </html>
    """
    resp.data = html
    resp.status_code = 200
    return resp

@app.route("/post-image", methods=["POST"])
def post_image():
    body = request.get_json(silent=True) or {}
    if not body and request.form:
        body = request.form.to_dict()

    badgeid = body.get("badgeid")
    verifcode = body.get("verifcode")
    VERIFICATION_URL = f"{VERIFICATION_STUB}{verifcode}"
    BADGE_DETAILS_URL = f"{BADGE_DETAILS_STUB}{badgeid}.html"
    BADGE_IMG_URL = f"{BADGE_IMG_STUB}{badgeid}.png"
    BADGE_NAME_UPPERCASE = (badgeid or "").upper()

    image_url = body.get("image_url", f"{BADGE_IMG_URL}")

    commentary = body.get("commentary") or (
        f"I just earned my Aerospike Academy {BADGE_NAME_UPPERCASE} Badge! 🎓\n\n"
        f"🚀 Details:\n"
        f"{BADGE_DETAILS_URL}\n\n"
        f"🔒 Verification:\n"
        f"{VERIFICATION_URL}"
    )

    img_title = body.get("title", "learn.aerospike.com")

    ukey = current_user_key()
    if ukey not in TOKENS:
        return "Connect LinkedIn first at /auth/linkedin/start", 400

    bearer = get_auth_header(ukey)
    if not bearer:
        return "Token missing/expired. Reconnect LinkedIn.", 401

    try:
        owner = TOKENS[ukey]["person_urn"]

        # 1) Register upload → asset URN (v2)
        upload_url, asset_urn = init_v2_asset_upload(owner_urn=owner, bearer_headers=bearer)

        # 2) Upload image bytes
        img = requests.get(image_url, timeout=20)
        img.raise_for_status()
        content_type = img.headers.get("Content-Type", "image/png")
        put_bytes_to_linkedin(upload_url, img.content, content_type=content_type)

        # 3) Create UGC image post
        payload = {
            "author": owner,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": commentary},
                    "shareMediaCategory": "IMAGE",
                    "media": [{
                        "status": "READY",
                        "media": asset_urn,
                        "title": {"text": img_title},
                    }]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        r = requests.post(
            UGC_POSTS_URL,
            headers={**bearer, "Content-Type": "application/json"},
            json=payload
        )
        print("UGC IMAGE RESP:", r.status_code, r.headers.get("Content-Type"), r.text[:400], "...")
        r.raise_for_status()

        post_urn = r.json().get("id")
        url = f"https://www.linkedin.com/feed/update/{post_urn}"
        return redirect(url)

    except requests.exceptions.HTTPError as e:
        return f"LinkedIn API Error: {e.response.text}", e.response.status_code
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}", 500

# ----- Main -----
if __name__ == "__main__":
    # dev server; for prod use gunicorn
    app.run(host="0.0.0.0", port=PORT, debug=True)
