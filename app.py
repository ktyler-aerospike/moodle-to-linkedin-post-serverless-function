import os
import json
import time
import secrets
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, request, session, jsonify
from dotenv import load_dotenv
from itsdangerous import URLSafeSerializer, BadSignature
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv(override=True)

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI")
PORT = int(os.getenv("PORT", "8083"))

# OIDC + posting scopes
SCOPES = ["openid", "profile", "w_member_social"]

# LinkedIn endpoints
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"

POSTS_URL = "https://api.linkedin.com/rest/posts"
IMAGES_INIT_URL = "https://api.linkedin.com/rest/images?action=initializeUpload"
ASSETS_REGISTER_URL = "https://api.linkedin.com/v2/assets?action=registerUpload"

BADGE_IMG_STUB = "https://catalog.learn.aerospike.com/img/badges/"
BADGE_DETAILS_STUB = "https://catalog.learn.aerospike.com/"
VERIFICATION_STUB = "https://learn.aerospike.com/admin/tool/certificate/index.php?code="

ALLOWED_START_PARAMS = ("badgeid", "verifcode")  # no underscores here; cleaner in URL

TOKENS = {}  # user_key -> { access_token, refresh_token?, expires_at, person_urn }


def _now() -> int:
    return int(time.time())


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", secrets.token_hex(32))

# Make cookies survive redirects and proxies nicely
app.config.update(
    SESSION_COOKIE_SECURE=True,   # only over HTTPS
    SESSION_COOKIE_SAMESITE="Lax",  # works for top-level OAuth redirect back
    PREFERRED_URL_SCHEME="https"
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Signed state helper (packs params so we don't rely on session)
STATE_SIGNER = URLSafeSerializer(app.secret_key, salt="li-state")


def make_state(data: dict) -> str:
    return STATE_SIGNER.dumps(data)


def read_state(s: str) -> dict:
    return STATE_SIGNER.loads(s)


# ------------- AUTH RELATED HELPERS -------------
# this function makes the diag(nostic) route helpful, without exposing secrets..

def mask(s: str):
    if not s:
        return None
    return s if len(s) < 6 else s[:3] + "…" + s[-3:]


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for tokens (OIDC access_token, optional refresh_token)."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    r = requests.post(TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    # Log status + a safe prefix of body for troubleshooting
    print("TOKEN RESP:", r.status_code, r.text[:200], "...")
    r.raise_for_status()
    tok = r.json()
    return {
        "access_token": tok["access_token"],
        "expires_at": _now() + int(tok.get("expires_in", 0)),
        "refresh_token": tok.get("refresh_token"),  # may be absent depending on your app config
        "refresh_token_expires_in": tok.get("refresh_token_expires_in"),
        # "id_token": tok.get("id_token"),  # not required since we use /userinfo
    }


def get_auth_header(user_key: str):
    rec = TOKENS.get(user_key)
    if not rec:
        return None
    return {"Authorization": f"Bearer {rec['access_token']}"}


def current_user_key():
    # Replace with your Moodle user id mapping. For demo we use remote_addr.
    return request.remote_addr or "demo-user"


# -------POSTING-RELATED HELPERS-------------------

def init_rest_image_upload(owner_urn: str, headers: dict) -> tuple[str, str]:
    """
    REST Images initializeUpload → returns (uploadUrl, image_urn).
    Use for Posts API thumbnails (content.article.thumbnail).
    """
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
    """
    PUT the raw image bytes to LinkedIn uploadUrl.
    Do NOT send LinkedIn-Version/Auth; the upload URL handles auth itself.
    """
    r = requests.put(upload_url, data=content_bytes, headers={"Content-Type": content_type})
    print("PUT upload:", r.status_code, r.text[:150], "...")
    r.raise_for_status()


def create_article_post(author_urn: str, thumbnail_urn: str, source_url: str, title: str, description: str, commentary: str, headers: dict):
    """Create an Article post via REST Posts API with explicit thumbnail."""
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
    """
    v2 Assets registerUpload → returns (uploadUrl, asset_urn).
    Use this for UGC IMAGE posts (the UGC media field takes an asset URN).
    """
    payload = {
        "registerUploadRequest": {
            "owner": owner_urn,
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "serviceRelationships": [
                {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
            ]
        }
    }
    # v2 endpoint: do NOT include LinkedIn-Version/X-RestLi headers
    v2_headers = {**bearer_headers, "Content-Type": "application/json"}
    r = requests.post(ASSETS_REGISTER_URL, headers=v2_headers, json=payload)
    print("v2 assets registerUpload:", r.status_code, r.text[:300], "...")
    r.raise_for_status()
    j = r.json()["value"]
    upload_url = j["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset_urn = j["asset"]  # urn:li:digitalmediaAsset:...
    return upload_url, asset_urn


# ------------- routes -------------
@app.route("/")
def home():
    return "Hello from Kristl's Cloud Run serverless function! Try /diag for diagnostic info, use /auth/linkedin/start to trigger the posting flow"


@app.route("/diag")
def diag():
    return {
        "LINKEDIN_CLIENT_ID": mask(CLIENT_ID),
        "LINKEDIN_REDIRECT_URI": REDIRECT_URI,
        "has_client_secret": bool(CLIENT_SECRET),
        "port": PORT,
        "scopes": " ".join(SCOPES),
        "session_cookie_samesite": app.config.get("SESSION_COOKIE_SAMESITE"),
        "session_cookie_secure": app.config.get("SESSION_COOKIE_SECURE"),
    }, 200


@app.route("/auth/linkedin/start")
def linkedin_start():
    if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI]):
        return "Missing envs: LINKEDIN_CLIENT_ID/SECRET/REDIRECT_URI", 500

    # Allow only known params and require them
    incoming = {k: v for k, v in request.args.items() if k in ALLOWED_START_PARAMS}
    if not incoming.get("badgeid") or not incoming.get("verifcode"):
        return "Missing required parameters: badgeid, verifcode", 400

    # Build signed state containing CSRF + your start params. This avoids losing them.
    csrf = secrets.token_urlsafe(24)
    state_payload = {"csrf": csrf, "params": incoming}
    state = make_state(state_payload)

    # Optional: store csrf as double-submit token (params are NOT stored in session)
    session["oauth_state_csrf"] = csrf

    query = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "scope": " ".join(SCOPES),
    }
    auth_url = f"{AUTH_URL}?{urlencode(query)}"
    print("AUTH URL:", auth_url)
    return redirect(auth_url)


@app.route("/auth/linkedin/callback")
def linkedin_callback():
    # Surface LinkedIn error if present
    if request.args.get("error"):
        return {
            "error": request.args.get("error"),
            "error_description": request.args.get("error_description"),
        }, 400

    raw_state = request.args.get("state")
    if not raw_state:
        return "Missing OAuth state.", 400

    try:
        st = read_state(raw_state)  # verifies signature
    except BadSignature:
        return "Invalid OAuth state.", 400

    # Optional CSRF double-submit check (won't block if cookie was lost)
    csrf_in_session = session.get("oauth_state_csrf")
    if csrf_in_session and st.get("csrf") != csrf_in_session:
        return "CSRF check failed.", 400

    params = st.get("params") or {}
    if not params.get("badgeid") or not params.get("verifcode"):
        return "Start parameters missing.", 400

    # Authorization code required
    code = request.args.get("code")
    if not code:
        return "Missing authorization code.", 400

    # Exchange code for tokens
    tokens = exchange_code_for_tokens(code)

    # OIDC userinfo: get stable subject to build author URN
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

    # Render the form with hidden inputs from the *verified* state
    def hidden_inputs(d):
        def esc(x):
            return (x or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return "".join(
            f'<input type="hidden" name="{k}" value="{esc(d[k])}"/>'
            for k in ALLOWED_START_PARAMS if k in d
        )

    return f"""
    <html>
      <head><title>LinkedIn Connected</title></head>
      <body style="font-family: Arial, sans-serif; text-align: center; padding-top: 40px;">
        <h2>✅ LinkedIn Connected.</h2>
        <p>You can now post your badge announcement to LinkedIn.</p>
        <form action="/post-image" method="post">
          {hidden_inputs(params)}
          <button type="submit" style="padding:10px 20px;font-size:16px;cursor:pointer;">
            Post My Badge Announcement
          </button>
        </form>
      </body>
    </html>
    """, 200


@app.route("/post-image", methods=["POST"])
def post_image():
    body = request.get_json(silent=True) or {}
    if not body and request.form:
        body = request.form.to_dict()

    badgeid = body.get("badgeid")
    verifcode = body.get("verifcode")

    if not (badgeid and verifcode):
        return "badgeid and verifcode are required.", 400

    VERIFICATION_URL = f"{VERIFICATION_STUB}{verifcode}"
    BADGE_DETAILS_URL = f"{BADGE_DETAILS_STUB}{badgeid}.html"
    BADGE_IMG_URL = f"{BADGE_IMG_STUB}{badgeid}.png"
    BADGE_NAME_UPPERCASE = badgeid.upper()

    image_url = body.get("image_url") or BADGE_IMG_URL

    if not (isinstance(image_url, str) and image_url.startswith("http")):
        return "Image URL invalid.", 400

    commentary = body.get("commentary") or (
        f"I just earned my Aerospike Academy {BADGE_NAME_UPPERCASE} Badge! 🎓\n\n"
        f"🚀 Details:\n{BADGE_DETAILS_URL}\n\n"
        f"🔒 Verification:\n{VERIFICATION_URL}"
    )

    img_title = body.get("title", "learn.aerospike.com")

    ukey = current_user_key()
    if ukey not in TOKENS:
        return "Connect LinkedIn first at /auth/linkedin/start", 400

    # Bearer only (no LinkedIn-Version headers for v2)
    bearer = get_auth_header(ukey)
    if not bearer:
        return "Token missing/expired. Reconnect LinkedIn.", 401

    try:
        owner = TOKENS[ukey]["person_urn"]

        # 1) v2 Assets: register upload → asset URN
        upload_url, asset_urn = init_v2_asset_upload(owner_urn=owner, bearer_headers=bearer)

        # 2) Upload the image bytes to the uploadUrl
        img = requests.get(image_url, timeout=20)
        img.raise_for_status()
        content_type = img.headers.get("Content-Type") or "image/png"
        put_bytes_to_linkedin(upload_url, img.content, content_type=content_type)

        # 3) Create UGC post that references the asset URN
        payload = {
            "author": owner,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": commentary},
                    "shareMediaCategory": "IMAGE",
                    "media": [{
                        "status": "READY",
                        "media": asset_urn,            # urn:li:digitalmediaAsset:...
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
            headers={**bearer, "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"},
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


# ------------- main -------------
if __name__ == "__main__":
    # dev server; for prod use gunicorn (see Dockerfile later)
    app.run(host="0.0.0.0", port=PORT, debug=True)
