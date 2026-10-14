from flask import Flask, render_template_string, request, jsonify, session, send_from_directory
import uuid
import json
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse

app = Flask(__name__)
# Set SECRET_KEY in the deployment environment. The fallback is for local development only.
app.secret_key = os.environ.get("SECRET_KEY", "local-development-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
DB_FILE = os.environ.get("DB_FILE", os.path.join(DATA_DIR, "database.json"))
# Store uploads beside the database by default so both can live on persistent storage.
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(DATA_DIR, "uploads"))
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
POST_LIFETIME_HOURS = 3
APP_PATCH = "admin-bootstrap-one-time"

os.makedirs(AVATAR_FOLDER, exist_ok=True)

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def json_body():
    """Return a JSON object or an empty dict for malformed/missing request bodies."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}

def get_role_config(role):
    roles = {
        "admin": {
            "name": "ผู้ดูแลระบบ",
            "badge": "👑",
            "bg_badge": "linear-gradient(90deg, #b8860b, #ffd700)",
            "text_color": "#ffd700"
        },
        "vip": {
            "name": "สมาชิก VIP",
            "badge": "⭐",
            "bg_badge": "linear-gradient(90deg, #8b00ff, #da70d6)",
            "text_color": "#da70d6"
        },
        "member": {
            "name": "สมาชิกทั่วไป",
            "badge": "👤",
            "bg_badge": "linear-gradient(90deg, #374151, #6b7280)",
            "text_color": "#9ca3af"
        }
    }
    return roles.get(role, roles["member"])

def load_database():
    default_data = {
        "users": {
            "admin": {
                "password": generate_password_hash(os.environ.get("ADMIN_PASSWORD", "admin123"), method='pbkdf2:sha256'),
                "role": "admin",
                "avatar": None,
                "bio": "ผู้ดูแลระบบ FM_Market",
                "created_at": datetime.now().strftime('%d/%m/%Y %H:%M')
            }
        },
        "posts": [],
        "messages": [],
        "mediation_rooms": [],
        "notifications": [],
        "news": [
            {"id": "n001", "title": "เปิดระบบ FM_Market", "date": "14 ตุลาคม 2026", "content": "ทุกฟีเจอร์ทำงานครบถ้วน"},
            {"id": "n002", "title": "⚠️ คำเตือนความปลอดภัย", "date": "14 ตุลาคม 2026", "content": "ห้ามโอนเงินให้ใครโดยตรง — ตกลงผ่านระบบ"}
        ],
        "categories": {
            "buy_money": {"name": "รับซื้อเงิน M", "icon": "💰", "color": "#10b981"},
            "sell_money": {"name": "ขายเงิน M", "icon": "💵", "color": "#ef4444"},
            "buy_item": {"name": "ไอเทม", "icon": "📦", "color": "#3b82f6"},
            "buy_car": {"name": "ยานพาหนะ", "icon": "🚗", "color": "#d4af37"},
            "buy_house": {"name": "บ้าน/ธุรกิจ", "icon": "🏠", "color": "#8b5cf6"},
            "other": {"name": "อื่นๆ", "icon": "📋", "color": "#6b7280"}
        },
        "settings": {"post_lifetime_hours": POST_LIFETIME_HOURS, "max_images_per_post": 5}
    }
    os.makedirs(os.path.dirname(os.path.abspath(DB_FILE)), exist_ok=True)
    if not os.path.exists(DB_FILE):
        data = default_data
    else:
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            # Do not overwrite a malformed existing database with defaults.
            # Fail loudly so the operator can restore a backup safely.
            raise RuntimeError(
                f"Database file could not be read: {DB_FILE}. "
                "Back up the file and repair/restore it before restarting."
            )
    for k in default_data:
        if k not in data:
            data[k] = default_data[k]
    # One-time admin bootstrap, controlled only through Render Environment.
    # The password is hashed and is never stored in source code.
    settings = data.get("settings")
    if not isinstance(settings, dict):
        settings = {}
        data["settings"] = settings
    bootstrap_username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "").strip()
    bootstrap_password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    if (bootstrap_username and bootstrap_password
            and not settings.get("_admin_bootstrap_completed")):
        users = data.get("users")
        if not isinstance(users, dict):
            users = {}
            data["users"] = users
        admin_user = users.get(bootstrap_username)
        if not isinstance(admin_user, dict):
            admin_user = {
                "avatar": None,
                "bio": "ผู้ดูแลระบบ FM_Market",
                "created_at": datetime.now().strftime('%d/%m/%Y %H:%M'),
                "profile_theme": "#d4af37",
                "profile_banner": None,
            }
            users[bootstrap_username] = admin_user
        admin_user["password"] = generate_password_hash(
            bootstrap_password, method="pbkdf2:sha256"
        )
        admin_user["role"] = "admin"
        admin_user.setdefault("avatar", None)
        admin_user.setdefault("bio", "")
        admin_user.setdefault("profile_theme", "#d4af37")
        admin_user.setdefault("profile_banner", None)
        admin_user.setdefault("created_at", datetime.now().strftime('%d/%m/%Y %H:%M'))
        settings["_admin_bootstrap_completed"] = True

    for uname in data["users"]:
        user = data["users"][uname]
        if not isinstance(user, dict):
            continue
        if "role" not in user:
            user["role"] = "member"
        if "avatar" not in user:
            user["avatar"] = None
        if "bio" not in user:
            user["bio"] = ""
        if "profile_theme" not in user:
            user["profile_theme"] = "#d4af37"
        if "profile_banner" not in user:
            user["profile_banner"] = None
    now = datetime.now()
    fresh_posts = []
    for p in data["posts"]:
        if not isinstance(p, dict):
            fresh_posts.append(p)
            continue
        try:
            post_time = datetime.strptime(p["time"], '%d/%m/%Y %H:%M')
            if now - post_time <= timedelta(hours=POST_LIFETIME_HOURS):
                fresh_posts.append(p)
        except Exception:
            fresh_posts.append(p)
    data["posts"] = fresh_posts
    save_database(data)
    return data

def save_database(data):
    # Atomic replacement prevents a partial JSON file if the process is interrupted.
    os.makedirs(os.path.dirname(os.path.abspath(DB_FILE)), exist_ok=True)
    temp_file = DB_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_file, DB_FILE)

@app.route('/')
def index():
    db = load_database()
    if 'user' not in session:
        return render_template_string(AUTH_PAGE)

    # A session can outlive a user record (for example after a database migration).
    # Clear only that stale browser session; never delete or reset database records.
    session_user = session.get('user') or {}
    uname = session_user.get('username') if isinstance(session_user, dict) else None
    users = db.get("users", {})
    if not isinstance(uname, str) or uname not in users:
        session.clear()
        return render_template_string(AUTH_PAGE)

    # Use the current role from the database rather than trusting an old cookie.
    session_user = {"username": uname, "role": users[uname].get("role", "member")}
    session['user'] = session_user

    # Older posts may reference a user who is no longer in the users dictionary.
    # Supply a display-only fallback so one stale post cannot crash the whole page.
    all_users = dict(users)
    for post in db.get("posts", []):
        if not isinstance(post, dict):
            continue
        author = post.get("author")
        if isinstance(author, str) and author not in all_users:
            all_users[author] = {
                "role": "member", "avatar": None, "bio": "",
                "profile_theme": "#d4af37", "profile_banner": None,
                "created_at": "-"
            }

    return render_template_string(
        MAIN_PAGE,
        posts=db.get("posts", []),
        news=db.get("news", []),
        categories=db.get("categories", {}),
        session_user=session_user,
        get_role_config=get_role_config,
        all_users=all_users
    )

@app.route('/api/upload-avatar', methods=['POST'])
def upload_avatar():
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"})
    if 'avatar' not in request.files:
        return jsonify({"success": False, "message": "ไม่พบไฟล์"})
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({"success": False, "message": "ยังไม่ได้เลือกไฟล์"})
    if not allowed_file(file.filename):
        return jsonify({"success": False, "message": "รองรับเฉพาะ .jpg .png .gif .webp"})
    ext = file.filename.rsplit(".", 1)[1].lower()
    fn = f"avatar_{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(AVATAR_FOLDER, fn))
    avatar_url = f"/uploads/avatars/{fn}"
    db = load_database()
    uname = session['user']['username']
    if db["users"][uname].get("avatar"):
        old_name = os.path.basename(db["users"][uname]["avatar"])
        old_path = os.path.join(AVATAR_FOLDER, old_name)
        if os.path.isfile(old_path):
            os.remove(old_path)
    db["users"][uname]["avatar"] = avatar_url
    save_database(db)
    return jsonify({"success": True, "avatar_url": avatar_url})

@app.route('/api/profile', methods=['GET'])
def get_profile():
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    db = load_database()
    session_user = session.get('user') or {}
    uname = session_user.get('username') if isinstance(session_user, dict) else None
    u = db.get("users", {}).get(uname) if isinstance(uname, str) else None
    if not isinstance(u, dict):
        session.clear()
        return jsonify({
            "success": False,
            "message": "ไม่พบบัญชีในฐานข้อมูล กรุณาเข้าสู่ระบบใหม่"
        }), 401
    role = u.get("role", "member")
    return jsonify({
        "success": True,
        "username": uname,
        "role": role,
        "role_info": get_role_config(role),
        "avatar": u.get("avatar"),
        "bio": u.get("bio", ""),
        "profile_theme": u.get("profile_theme", "#d4af37"),
        "profile_banner": u.get("profile_banner"),
        "created_at": u.get("created_at", "-")
    })

@app.route('/api/profile/<username>', methods=['GET'])
def get_public_profile(username):
    """Expose only public profile fields; never return passwords or private account data."""
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    db = load_database()
    user = db["users"].get(username)
    if not user:
        return jsonify({"success": False, "message": "ไม่พบผู้ใช้นี้"}), 404
    role = user.get("role", "member")
    return jsonify({
        "success": True,
        "username": username,
        "role": role,
        "role_info": get_role_config(role),
        "avatar": user.get("avatar"),
        "bio": user.get("bio", ""),
        "profile_theme": user.get("profile_theme", "#d4af37"),
        "profile_banner": user.get("profile_banner"),
        "created_at": user.get("created_at", "-")
    })

@app.route('/api/profile/update', methods=['POST'])
def update_profile():
    if 'user' not in session:
        return jsonify({"success": False})
    db = load_database()
    uname = session['user']['username']
    d = json_body()
    if "bio" in d:
        bio = d.get("bio")
        if not isinstance(bio, str):
            return jsonify({"success": False, "message": "ข้อมูลโปรไฟล์ไม่ถูกต้อง"}), 400
        db["users"][uname]["bio"] = bio.strip()[:500]
    theme = d.get("profile_theme")
    if theme is not None:
        import re
        if not isinstance(theme, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", theme):
            return jsonify({"success": False, "message": "สีธีมไม่ถูกต้อง"}), 400
        db["users"][uname]["profile_theme"] = theme
    save_database(db)
    return jsonify({"success": True, "message": "บันทึกโปรไฟล์เรียบร้อย"})

@app.route('/api/admin/set-role' , methods=['POST'])
def set_role():
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    db = load_database()
    actor = db["users"].get(session["user"].get("username"), {})
    # Never trust the role stored in a client-side session cookie; roles may have changed.
    if actor.get("role") != "admin":
        session.pop("user", None)
        return jsonify({"success": False, "message": "ไม่มีสิทธิ์"}), 403
    d = json_body()
    target_user = d.get("username", "")
    if not isinstance(target_user, str):
        return jsonify({"success": False, "message": "ชื่อผู้ใช้ไม่ถูกต้อง"}), 400
    target_user = target_user.strip()
    new_role = d.get("role")
    if new_role not in ["admin", "vip", "member"]:
        return jsonify({"success": False, "message": "ยศไม่ถูกต้อง"}), 400
    if target_user not in db["users"]:
        return jsonify({"success": False, "message": "ไม่พบผู้ใช้"}), 404
    if db["users"][target_user].get("role") == "admin" and new_role != "admin":
        admin_count = sum(1 for user in db["users"].values() if user.get("role") == "admin")
        if admin_count <= 1:
            return jsonify({"success": False, "message": "ต้องมีผู้ดูแลระบบอย่างน้อยหนึ่งบัญชี"}), 400
    db["users"][target_user]["role"] = new_role
    save_database(db)
    if target_user == session["user"].get("username"):
        session["user"]["role"] = new_role
    return jsonify({"success": True, "message": f"ตั้งยศ {new_role} ให้ {target_user} สำเร็จ"})

@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"})
    if 'image' not in request.files:
        return jsonify({"success": False, "message": "ไม่พบไฟล์"})
    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "message": "ยังไม่ได้เลือกไฟล์"})
    if not allowed_file(file.filename):
        return jsonify({"success": False, "message": "รองรับเฉพาะ .jpg .png .gif .webp"})
    ext = file.filename.rsplit(".", 1)[1].lower()
    fn = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_FOLDER, fn))
    return jsonify({"success": True, "url": f"/uploads/{fn}"})

@app.route('/api/register', methods=['POST'])
def register():
    db = load_database()
    d = json_body()
    u = str(d.get("username", "")).strip()
    p = d.get("password", "")
    if len(u) < 2 or len(u) > 32 or any(ord(c) < 32 for c in u):
        return jsonify({"success": False, "message": "ชื่อต้อง 2 ตัวอักษรขึ้นไป"})
    if u in db['users']:
        return jsonify({"success": False, "message": "ชื่อนี้มีคนใช้แล้ว"})
    if not isinstance(p, str) or len(p) < 4 or len(p) > 256:
        return jsonify({"success": False, "message": "รหัสผ่านต้อง 4 ตัวขึ้นไป"})
    hashed_pw = generate_password_hash(p, method='pbkdf2:sha256')
    db['users'][u] = {
        "password": hashed_pw,
        "role": "member",
        "avatar": None,
        "bio": "",
        "created_at": datetime.now().strftime('%d/%m/%Y %H:%M')
    }
    save_database(db)
    session.clear()
    session['user'] = {"username": u, "role": "member"}
    return jsonify({"success": True, "user": {"username": u, "role": "member"}})

@app.route('/api/login', methods=['POST'])
def login():
    db = load_database()
    d = json_body()
    u = str(d.get("username", "")).strip()
    p = d.get("password", "")
    user = db['users'].get(u)
    if not user:
        return jsonify({"success": False, "message": "ชื่อหรือรหัสผ่านไม่ถูกต้อง"})
    if not isinstance(p, str) or not check_password_hash(user['password'], p):
        return jsonify({"success": False, "message": "ชื่อหรือรหัสผ่านไม่ถูกต้อง"})
    session.clear()
    session['user'] = {"username": u, "role": user["role"]}
    return jsonify({"success": True, "user": session['user']})

@app.route('/api/logout', methods=['GET'])
def logout():
    session.pop('user', None)
    return jsonify({"success": True})

@app.route('/api/post', methods=['POST'])
def create_post():
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    db = load_database()
    session_user = session.get('user') or {}
    uname = session_user.get('username') if isinstance(session_user, dict) else None
    if not isinstance(uname, str) or uname not in db.get("users", {}):
        session.clear()
        return jsonify({
            "success": False,
            "message": "ไม่พบบัญชีในฐานข้อมูล กรุณาเข้าสู่ระบบใหม่"
        }), 401
    d = json_body()
    category = d.get("category")
    title = d.get("title", "")
    detail = d.get("detail", "")
    images = d.get("images", [])
    if category not in db["categories"]:
        return jsonify({"success": False, "message": "หมวดหมู่ไม่ถูกต้อง"})
    if not isinstance(title, str) or not title.strip():
        return jsonify({"success": False, "message": "กรุณากรอกหัวข้อ"})
    if not isinstance(detail, str) or not isinstance(images, list):
        return jsonify({"success": False, "message": "ข้อมูลประกาศไม่ถูกต้อง"})
    images = [url for url in images[:5] if isinstance(url, str) and url.startswith("/uploads/")]
    post = {
        "id": str(uuid.uuid4())[:8],
        "category": category,
        "title": title.strip()[:120],
        "detail": detail.strip()[:5000],
        "images": images,
        "author": uname,
        "time": datetime.now().strftime('%d/%m/%Y %H:%M'),
        "status": "active"
    }
    db["posts"].insert(0, post)
    save_database(db)
    return jsonify({"success": True, "posts": db["posts"]})

@app.route('/api/post/<post_id>', methods=['DELETE'])
def delete_post(post_id):
    if 'user' not in session:
        return jsonify({"success": False})
    db = load_database()
    uname = session['user']['username']
    current_user = db["users"].get(uname, {})
    is_admin = current_user.get("role") == "admin"
    if not current_user:
        session.pop("user", None)
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบใหม่"}), 401
    keep = []
    found = False
    for p in db["posts"]:
        if p["id"] == post_id and (p["author"] == uname or is_admin):
            found = True
        else:
            keep.append(p)
    if not found:
        return jsonify({"success": False, "message": "ไม่พบหรือไม่มีสิทธิ์ลบ"})
    db["posts"] = keep
    save_database(db)
    return jsonify({"success": True})

def message_datetime(message):
    """Parse legacy message timestamps for reliable chronological ordering."""
    try:
        return datetime.strptime(message.get("time", ""), "%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return datetime.min


@app.route('/api/chat-overview', methods=['GET'])
def chat_overview():
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    me = session['user']['username']
    db = load_database()
    conversations = {}
    # Build a single inbox entry per conversation, regardless of who sent first.
    for msg in db.get("messages", []):
        sender, receiver = msg.get("from"), msg.get("to")
        if me not in (sender, receiver):
            continue
        other = receiver if sender == me else sender
        if not other or other not in db.get("users", {}):
            continue
        current = conversations.get(other)
        if current is None or message_datetime(msg) >= message_datetime(current["_message"]):
            conversations[other] = {
                "last_msg": msg.get("text", ""),
                "type": msg.get("type", "text"),
                "time": msg.get("time", ""),
                "unread": 0,
                "_message": msg,
            }
        if receiver == me and not msg.get("read", False):
            # Count unread messages independently of which message is newest.
            conversations.setdefault(other, {"last_msg": "", "type": "text", "time": "", "unread": 0, "_message": msg})["unread"] += 1
    for name, item in conversations.items():
        item.pop("_message", None)
        user = db.get("users", {}).get(name, {})
        item["avatar"] = user.get("avatar") if isinstance(user, dict) else None
        item["role"] = user.get("role", "member") if isinstance(user, dict) else "member"
    total_unread = sum(item["unread"] for item in conversations.values())
    return jsonify({"success": True, "contacts": conversations, "total_unread": total_unread})


@app.route('/api/chat-users', methods=['GET'])
def chat_users():
    """Search existing members so users can start a conversation without a prior message."""
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    db = load_database()
    current = (session.get('user') or {}).get('username')
    query = (request.args.get('q') or '').strip().casefold()[:60]
    users = db.get("users", {})
    results = []
    if isinstance(users, dict):
        for username, info in users.items():
            if username == current or not isinstance(info, dict):
                continue
            if query and query not in str(username).casefold():
                continue
            results.append({
                "username": username,
                "avatar": info.get("avatar"),
                "role": info.get("role", "member"),
                "bio": str(info.get("bio", ""))[:120]
            })
    results.sort(key=lambda u: (not u["username"].casefold().startswith(query), u["username"].casefold()))
    return jsonify({"success": True, "users": results[:30]})


@app.route('/api/conversation/<partner>', methods=['GET'])
def get_conversation(partner):
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    me = session['user']['username']
    db = load_database()
    if partner == me or partner not in db.get("users", {}):
        return jsonify({"success": False, "message": "ไม่พบผู้ใช้ที่ต้องการแชท"}), 404
    conv = [m for m in db.get("messages", [])
            if (m.get("from") == me and m.get("to") == partner) or
               (m.get("from") == partner and m.get("to") == me)]
    changed = False
    for msg in conv:
        if msg.get("to") == me and not msg.get("read", False):
            msg["read"] = True
            changed = True
    # Clear matching message notifications as soon as the recipient opens the thread.
    for notif in db.get("notifications", []):
        if notif.get("type") == "message" and notif.get("from") == partner and notif.get("to") == me and not notif.get("read", False):
            notif["read"] = True
            changed = True
    if changed:
        save_database(db)
    conv.sort(key=message_datetime)
    return jsonify({"success": True, "messages": conv, "partner": partner})


@app.route('/api/conversation/<partner>/read', methods=['POST'])
def mark_conversation_read(partner):
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    me = session['user']['username']
    db = load_database()
    changed = False
    for msg in db.get("messages", []):
        if msg.get("from") == partner and msg.get("to") == me and not msg.get("read", False):
            msg["read"] = True
            changed = True
    for notif in db.get("notifications", []):
        if notif.get("type") == "message" and notif.get("from") == partner and notif.get("to") == me and not notif.get("read", False):
            notif["read"] = True
            changed = True
    if changed:
        save_database(db)
    return jsonify({"success": True})


@app.route('/api/send-message', methods=['POST'])
def send_message():
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    d = json_body()
    db = load_database()
    me = session['user']['username']
    receiver = d.get("to")
    text = d.get("text", "")
    msg_type = d.get("type", "text")
    if not isinstance(receiver, str) or not isinstance(text, str):
        return jsonify({"success": False, "message": "ข้อมูลไม่ถูกต้อง"}), 400
    text = text.strip()
    if not receiver or not text or len(text) > 2000 or receiver == me or receiver not in db["users"]:
        return jsonify({"success": False, "message": "ข้อมูลไม่ถูกต้อง"}), 400
    if msg_type not in ("text", "gif"):
        return jsonify({"success": False, "message": "รูปแบบข้อความไม่ถูกต้อง"}), 400
    if msg_type == "gif":
        parsed = urlparse(text)
        host = (parsed.hostname or "").lower()
        allowed_gif_hosts = ("media.tenor.com", "tenor.com", "media.giphy.com", "i.giphy.com", "giphy.com")
        if parsed.scheme != "https" or not any(host == h or host.endswith("." + h) for h in allowed_gif_hosts):
            return jsonify({"success": False, "message": "กรุณาใช้ลิงก์ GIF จาก Tenor หรือ GIPHY ที่ขึ้นต้นด้วย https://"}), 400
    new_msg = {
        "id": str(uuid.uuid4()),
        "from": me,
        "to": receiver,
        "text": text,
        "type": msg_type,
        "time": datetime.now().strftime('%d/%m/%Y %H:%M'),
        "read": False
    }
    db.setdefault("messages", []).append(new_msg)
    db.setdefault("notifications", []).append({
        "id": str(uuid.uuid4()),
        "type": "message",
        "from": me,
        "to": receiver,
        "text": f"มีข้อความใหม่จาก {me}: {text[:30]}{'...' if len(text) > 30 else ''}",
        "time": new_msg["time"],
        "read": False
    })
    # The message and notification are written to the database file before success is returned.
    save_database(db)
    return jsonify({"success": True, "message": new_msg})


@app.route('/api/presence', methods=['POST'])
def update_presence():
    """Heartbeat used to determine which admins are currently online."""
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    me = (session.get('user') or {}).get('username')
    db = load_database()
    user = db.get('users', {}).get(me)
    if not isinstance(user, dict):
        session.clear()
        return jsonify({"success": False, "message": "ไม่พบบัญชี กรุณาเข้าสู่ระบบใหม่"}), 401
    user['_presence_at'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    save_database(db)
    return jsonify({"success": True})


def _parse_presence(value):
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
    except (TypeError, ValueError):
        return None


def _active_mediation_for_user(db, username):
    return [r for r in db.get('mediation_rooms', [])
            if isinstance(r, dict) and r.get('status') == 'active'
            and username in r.get('participants', [])]


@app.route('/api/mediation/available-admins', methods=['GET'])
def mediation_available_admins():
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    db = load_database()
    now = datetime.now()
    busy = {r.get('admin') for r in db.get('mediation_rooms', [])
            if isinstance(r, dict) and r.get('status') == 'active'}
    admins = []
    for username, user in db.get('users', {}).items():
        if not isinstance(user, dict) or user.get('role') != 'admin':
            continue
        seen = _parse_presence(user.get('_presence_at'))
        online = bool(seen and (now - seen).total_seconds() <= 75)
        if online and username not in busy and username != (session.get('user') or {}).get('username'):
            admins.append({"username": username, "avatar": user.get('avatar')})
    return jsonify({"success": True, "admins": admins})


@app.route('/api/mediation/create', methods=['POST'])
def create_mediation():
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    d = json_body()
    me = (session.get('user') or {}).get('username')
    partner = d.get('partner')
    if not isinstance(partner, str) or not partner or partner == me:
        return jsonify({"success": False, "message": "กรุณาเลือกคู่สนทนาที่ถูกต้อง"}), 400
    db = load_database()
    users = db.get('users', {})
    if me not in users or partner not in users:
        return jsonify({"success": False, "message": "ไม่พบบัญชีผู้ใช้ในฐานข้อมูล"}), 404
    existing = next((r for r in db.get('mediation_rooms', [])
                     if isinstance(r, dict) and r.get('status') == 'active'
                     and set(r.get('pair', [])) == {me, partner}), None)
    if existing:
        return jsonify({"success": True, "room": existing, "existing": True})
    now = datetime.now()
    busy = {r.get('admin') for r in db.get('mediation_rooms', [])
            if isinstance(r, dict) and r.get('status') == 'active'}
    available = []
    for username, user in users.items():
        if not isinstance(user, dict) or user.get('role') != 'admin' or username in busy:
            continue
        seen = _parse_presence(user.get('_presence_at'))
        if seen and (now - seen).total_seconds() <= 75:
            available.append(username)
    if not available:
        return jsonify({"success": False, "message": "ขณะนี้ไม่มีแอดมินที่ออนไลน์และว่าง กรุณาลองใหม่ภายหลัง"}), 409
    available.sort(key=str.casefold)
    admin = available[0]
    room = {
        "id": str(uuid.uuid4()),
        "pair": [me, partner],
        "admin": admin,
        "participants": [me, partner, admin],
        "status": "active",
        "created_at": datetime.now().strftime('%d/%m/%Y %H:%M'),
        "messages": []
    }
    db.setdefault('mediation_rooms', []).append(room)
    db.setdefault('notifications', []).extend([
        {"id": str(uuid.uuid4()), "type": "mediation", "from": me, "to": partner,
         "text": f"{me} เชิญแอดมิน {admin} เข้าร่วมเป็นคนกลางในการซื้อขาย", "time": room['created_at'], "read": False},
        {"id": str(uuid.uuid4()), "type": "mediation", "from": me, "to": admin,
         "text": f"มีคำขอให้เป็นคนกลางระหว่าง {me} และ {partner}", "time": room['created_at'], "read": False}
    ])
    save_database(db)
    return jsonify({"success": True, "room": room})


@app.route('/api/mediation/active', methods=['GET'])
def active_mediations():
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    me = (session.get('user') or {}).get('username')
    db = load_database()
    rooms = []
    for room in db.get('mediation_rooms', []):
        if isinstance(room, dict) and room.get('status') == 'active' and me in room.get('participants', []):
            rooms.append({k: room.get(k) for k in ('id', 'pair', 'admin', 'participants', 'status', 'created_at')})
    return jsonify({"success": True, "rooms": rooms})


@app.route('/api/mediation/<room_id>', methods=['GET'])
def get_mediation(room_id):
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    me = (session.get('user') or {}).get('username')
    db = load_database()
    room = next((r for r in db.get('mediation_rooms', []) if isinstance(r, dict) and r.get('id') == room_id), None)
    if not room or me not in room.get('participants', []):
        return jsonify({"success": False, "message": "ไม่พบห้องคนกลาง"}), 404
    if room.get('status') != 'active':
        return jsonify({"success": False, "ended": True, "message": "การซื้อขายนี้สิ้นสุดแล้ว"}), 410
    return jsonify({"success": True, "room": room, "is_admin": me == room.get('admin')})


@app.route('/api/mediation/<room_id>/message', methods=['POST'])
def send_mediation_message(room_id):
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    me = (session.get('user') or {}).get('username')
    d = json_body()
    text = d.get('text', '')
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > 2000:
        return jsonify({"success": False, "message": "ข้อความต้องมีความยาว 1–2000 ตัวอักษร"}), 400
    db = load_database()
    room = next((r for r in db.get('mediation_rooms', []) if isinstance(r, dict) and r.get('id') == room_id), None)
    if not room or me not in room.get('participants', []):
        return jsonify({"success": False, "message": "ไม่มีสิทธิ์เข้าถึงห้องนี้"}), 403
    if room.get('status') != 'active':
        return jsonify({"success": False, "message": "ห้องนี้สิ้นสุดการซื้อขายแล้ว"}), 410
    msg = {"id": str(uuid.uuid4()), "from": me, "text": text.strip(),
           "time": datetime.now().strftime('%d/%m/%Y %H:%M')}
    room.setdefault('messages', []).append(msg)
    save_database(db)
    return jsonify({"success": True, "message": msg})


@app.route('/api/mediation/<room_id>/end', methods=['POST'])
def end_mediation(room_id):
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    me = (session.get('user') or {}).get('username')
    db = load_database()
    room = next((r for r in db.get('mediation_rooms', []) if isinstance(r, dict) and r.get('id') == room_id), None)
    if not room or me not in room.get('participants', []):
        return jsonify({"success": False, "message": "ไม่พบห้องคนกลาง"}), 404
    # Only the assigned admin can end the sale; participants cannot bypass the UI.
    if me != room.get('admin'):
        return jsonify({"success": False, "message": "เฉพาะแอดมินคนกลางที่ได้รับมอบหมายเท่านั้นที่จบการขายได้"}), 403
    if room.get('status') != 'active':
        return jsonify({"success": True, "already_ended": True})
    room['status'] = 'ended'
    room['ended_at'] = datetime.now().strftime('%d/%m/%Y %H:%M')
    room['ended_by'] = me
    for username in room.get('participants', []):
        db.setdefault('notifications', []).append({
            "id": str(uuid.uuid4()), "type": "mediation_ended", "from": me, "to": username,
            "text": f"แอดมิน {me} จบการขายแล้ว ห้องคนกลางถูกปิด", "time": room['ended_at'], "read": False
        })
    save_database(db)
    return jsonify({"success": True, "message": "จบการขายและปิดห้องคนกลางแล้ว"})


@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    if 'user' not in session:
        return jsonify({"success": False})
    me = session['user']['username']
    db = load_database()
    notifs = [n for n in db["notifications"] if n["to"] == me]
    unread_count = sum(1 for n in notifs if not n.get("read"))
    return jsonify({"success": True, "notifications": notifs, "unread_count": unread_count})

@app.route('/api/notifications/mark-read', methods=['POST'])
def mark_notif_read():
    if 'user' not in session:
        return jsonify({"success": False})
    me = session['user']['username']
    db = load_database()
    for n in db["notifications"]:
        if n["to"] == me:
            n["read"] = True
    save_database(db)
    return jsonify({"success": True})

AUTH_PAGE = '''
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>เข้าสู่ระบบ — FM_Market</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:"Segoe UI",sans-serif}
:root{--bg:#050508;--card:#12121a;--gold:#d4af37;--gold2:#f0c808;--text:#fff;--text2:#a0a0b5;--border:#282838;--error:#e53935}
body{background:linear-gradient(180deg,#000,#050508);color:var(--text);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.wrap{max-width:420px;width:100%}
.logo{text-align:center;margin-bottom:40px}
.logo h1{font-size:2.4rem}
.logo span{color:var(--gold)}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:32px;box-shadow:0 10px 40px rgba(0,0,0,.5)}
.tabs{display:flex;border-bottom:1px solid var(--border);margin-bottom:24px}
.tab{flex:1;padding:14px;text-align:center;cursor:pointer;font-weight:700;color:var(--text2);border-bottom:3px solid transparent}
.tab.active{color:var(--gold);border-color:var(--gold)}
form{display:none;animation:fade .3s ease}
form.active{display:block}
@keyframes fade{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
input{width:100%;padding:14px 16px;background:#0a0a10;border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:1rem;margin-bottom:14px}
input:focus{outline:none;border-color:var(--gold)}
button[type=submit]{width:100%;padding:14px;background:linear-gradient(90deg,var(--gold),var(--gold2));border:none;border-radius:8px;font-size:1rem;font-weight:800;color:#000;cursor:pointer;margin-top:6px;transition:transform .2s}
button[type=submit]:hover{transform:translateY(-2px)}
.warn{margin-top:18px;padding:12px;background:rgba(196,30,58,.1);border:1px solid rgba(196,30,58,.3);border-radius:8px;font-size:.85rem;color:#ff9999;text-align:center}
.error-msg{background:rgba(229,57,53,.1);border:1px solid rgba(229,57,53,.4);color:#ff6b6b;padding:10px 14px;border-radius:8px;margin-bottom:16px;text-align:center;display:none}
.error-msg.show{display:block}
</style>
</head>
<body>
<div class="wrap">
  <div class="logo"><h1>FM<span>_Market</span></h1></div>
  <div class="card">
    <div class="tabs">
      <div class="tab active" onclick="sw('login')">เข้าสู่ระบบ</div>
      <div class="tab" onclick="sw('reg')">สมัครสมาชิก</div>
    </div>
    <div id="loginErr" class="error-msg"></div>
    <form id="login" class="active" onsubmit="doL(event)">
      <input type="text" id="lu" placeholder="ชื่อผู้ใช้" required autocomplete="username">
      <input type="password" id="lp" placeholder="รหัสผ่าน" required autocomplete="current-password">
      <button type="submit">เข้าสู่ระบบ</button>
    </form>
    <div id="regErr" class="error-msg"></div>
    <form id="reg" onsubmit="doR(event)">
      <input type="text" id="ru" placeholder="ตั้งชื่อผู้ใช้" required autocomplete="username">
      <input type="password" id="rp" placeholder="ตั้งรหัสผ่าน (4 ตัวขึ้นไป)" required autocomplete="new-password">
      <button type="submit">สร้างบัญชี</button>
    </form>
    <div class="warn">⚠️ ห้ามโอนเงินให้ใครโดยตรง — ใช้แอดมินกลางเท่านั้น</div>
  </div>
</div>
<script>
function sw(t){
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('form').forEach(x=>x.classList.remove('active'));
  document.getElementById('loginErr').style.display='none';
  document.getElementById('regErr').style.display='none';
  if(t==='login'){
    document.querySelectorAll('.tab')[0].classList.add('active');
    document.getElementById('login').classList.add('active');
  } else {
    document.querySelectorAll('.tab')[1].classList.add('active');
    document.getElementById('reg').classList.add('active');
  }
}
async function doL(e){
  e.preventDefault();
  document.getElementById('loginErr').style.display='none';
  const r=await fetch('/api/login',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:document.getElementById('lu').value,password:document.getElementById('lp').value})
  });
  const d=await r.json();
  if(d.success){alert('✅ เข้าสู่ระบบสำเร็จ');window.location.href='/';}
  else{const b=document.getElementById('loginErr');b.textContent='❌ '+d.message;b.style.display='block';}
}
async function doR(e){
  e.preventDefault();
  document.getElementById('regErr').style.display='none';
  const r=await fetch('/api/register',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:document.getElementById('ru').value,password:document.getElementById('rp').value})
  });
  const d=await r.json();
  if(d.success){alert('✅ สมัครสำเร็จ! กำลังเข้าสู่ระบบ...');window.location.href='/';}
  else{const b=document.getElementById('regErr');b.textContent='❌ '+d.message;b.style.display='block';}
}
</script>
</body>
</html>
'''

MAIN_PAGE = r'''
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FM_Market — ตลาดซื้อขาย</title>
<style>
:root{--bg:#050508;--card:#12121a;--gold:#d4af37;--gold2:#f0c808;--blue:#2563eb;--red:#c41e3a;--text:#fff;--soft:#9090a5;--border:#282838;--r:14px}
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui,sans-serif}
body{background:var(--bg);color:var(--text);line-height:1.6;padding-bottom:80px}
header{position:sticky;top:0;z-index:999;background:rgba(5,5,8,.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:14px 20px}
.head{max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}
.brand{font-size:1.4rem;font-weight:900;cursor:pointer}
.brand span{color:var(--gold)}
.nav{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.btn{padding:9px 16px;border:none;border-radius:var(--r);font-weight:700;transition:.2s;cursor:pointer}
.btn:hover{transform:translateY(-2px)}
.btn-gold{background:linear-gradient(90deg,var(--gold),var(--gold2));color:#000}
.btn-blue{background:var(--blue);color:#fff}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--text)}
.btn-sm{padding:6px 12px;font-size:.85rem}
.btn-red{background:var(--red);color:#fff}
.badge{font-size:.7rem;padding:3px 8px;border-radius:12px;font-weight:700}
.badge-admin{background:var(--red);color:#fff}
.badge-member{background:var(--blue);color:#fff}
.notif-wrap,.chat-wrap,.profile-wrap{position:relative}
.bell-btn,.profile-btn{background:transparent;border:none;color:var(--text);font-size:1.2rem;padding:6px 10px;cursor:pointer;position:relative}
.badge-count{position:absolute;top:-2px;right:-4px;background:var(--red);color:#fff;font-size:.65rem;min-width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;transform:scale(0);transition:.2s}
.badge-count.show{transform:scale(1)}
.dropdown-panel{position:absolute;top:100%;right:0;margin-top:8px;width:340px;background:var(--card);border:1px solid var(--border);border-radius:var(--r);box-shadow:0 10px 40px rgba(0,0,0,.5);display:none;flex-direction:column;max-height:480px;overflow:hidden;z-index:2000}
.dropdown-panel.show{display:flex}
.panel-head{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
.panel-title{font-weight:700}
.panel-actions button{background:none;border:none;color:var(--soft);font-size:.8rem;cursor:pointer}
.panel-list{overflow-y:auto;flex:1}
.panel-item{padding:12px 16px;border-bottom:1px solid var(--border);cursor:pointer;transition:.2s}
.panel-item:hover{background:rgba(37,99,235,.1)}
.panel-item.unread{background:rgba(212,175,55,.12);border-left:3px solid var(--gold)}
.panel-item-name{font-weight:600;font-size:.9rem}
.panel-item-text{font-size:.85rem;color:var(--soft);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.panel-item-time{display:inline-flex;align-items:center;gap:5px;margin-top:8px;padding:4px 9px;border:1px solid rgba(212,175,55,.18);border-radius:999px;background:rgba(212,175,55,.08);color:#c9b77d;font-size:.72rem;line-height:1.2;font-weight:500;letter-spacing:.01em}.panel-item-time::before{content:"◷";font-size:.82rem;opacity:.9}.panel-item.unread .panel-item-time{background:rgba(212,175,55,.14);color:#f0d98a}
.empty-state{padding:30px;text-align:center;color:var(--soft);font-size:.9rem}
.chat-overlay{position:fixed;inset:0;background:transparent;z-index:3000;display:none;align-items:flex-end;justify-content:flex-end;padding:88px 22px 86px;pointer-events:none}
.chat-overlay.show{display:flex}
.chat-window{pointer-events:auto;width: min(380px, calc(100vw - 28px));background:var(--card);border:1px solid #343449;border-radius:18px;display:flex;flex-direction:column;height:min(560px, calc(100vh - 120px));box-shadow:0 18px 55px rgba(0,0,0,.62);overflow:hidden;animation:chatPop .18s ease-out}
@keyframes chatPop{from{opacity:0;transform:translateY(12px) scale(.98)}to{opacity:1;transform:translateY(0) scale(1)}}
.chat-header{padding:13px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;background:linear-gradient(110deg,#191925,#11111a)}
.chat-close{background:#252535;border:none;color:var(--soft);font-size:1.25rem;width:30px;height:30px;border-radius:50%;cursor:pointer}
.chat-messages{flex:1;padding:16px;overflow-y:auto;min-height:160px;background:#0a0a10;display:flex;flex-direction:column;gap:10px}
.msg-bubble{max-width:84%;padding:10px 13px;border-radius:18px;line-height:1.4;overflow-wrap:anywhere}
.msg-me{background:linear-gradient(135deg,#d4af37,#f0c808);color:#15120a;align-self:flex-end;border-bottom-right-radius:5px}
.msg-other{background:#252535;color:#f5f5f8;align-self:flex-start;border-bottom-left-radius:5px}
.msg-time{font-size:.68rem;color:var(--soft);margin-top:4px;text-align:right}
.msg-gif{display:block;width:min(230px,65vw);max-height:220px;object-fit:contain;border-radius:12px;background:#15151e}
.mediation-controls{display:flex;gap:7px;flex-wrap:wrap;padding:9px 10px;border-bottom:1px solid var(--border);background:#15151f}
.mediation-invite-btn,.mediation-end-btn,.mediation-leave-btn{border:1px solid rgba(212,175,55,.35);border-radius:10px;padding:8px 10px;font-size:.78rem;font-weight:700;cursor:pointer;background:rgba(212,175,55,.1);color:#f3d875}
.mediation-end-btn{background:linear-gradient(90deg,#16804a,#22a05a);border-color:#22a05a;color:white}
.mediation-leave-btn{background:#252535;color:#ddd;border-color:#38384a}
.mediation-info{width:100%;font-size:.75rem;color:#c8c8d5;line-height:1.5}
.chat-input-area{display:flex;align-items:center;gap:7px;padding:10px;border-top:1px solid var(--border);background:#12121a}
.chat-input-area input{min-width:0;flex:1;background:#0a0a10;border:1px solid var(--border);border-radius:18px;padding:10px 13px;color:var(--text);font-size:.9rem}
.chat-tool-btn{flex:0 0 auto;border:1px solid #333348;background:#20202d;color:#f6d86a;border-radius:50%;width:36px;height:36px;cursor:pointer;font-weight:800}
.chat-send-btn{flex:0 0 auto;border:0;background:linear-gradient(90deg,var(--gold),var(--gold2));color:#111;border-radius:18px;padding:10px 13px;font-weight:800;cursor:pointer}
.emoji-picker{display:none;grid-template-columns:repeat(8,1fr);gap:4px;padding:10px;background:#181823;border-top:1px solid var(--border);max-height:150px;overflow:auto}
.emoji-picker.show{display:grid}
.emoji-choice{border:0;background:transparent;border-radius:7px;padding:5px;font-size:1.25rem;cursor:pointer}.emoji-choice:hover{background:#303044}
.gif-panel{display:none;gap:7px;padding:10px;background:#181823;border-top:1px solid var(--border)}
.gif-panel.show{display:flex;flex-wrap:wrap}
.gif-panel input{min-width:0;flex:1;background:#090910;border:1px solid var(--border);border-radius:9px;padding:9px;color:#fff}
.gif-help{width:100%;font-size:.72rem;color:var(--soft)}
.chat-launcher{position:fixed;right:22px;bottom:20px;z-index:2999;width:58px;height:58px;border:2px solid rgba(255,255,255,.18);border-radius:50%;background:linear-gradient(135deg,#d4af37,#f0c808);color:#17130a;font-size:1.55rem;box-shadow:0 8px 25px rgba(0,0,0,.45);cursor:pointer;transition:transform .2s}
.chat-launcher:hover{transform:translateY(-3px) scale(1.03)}
.chat-wrap .dropdown-panel{position:fixed;top:auto;right:22px;bottom:88px;width:min(360px,calc(100vw - 28px));max-height:min(520px,calc(100vh - 130px))}
.chat-search-wrap{padding:10px 12px;border-bottom:1px solid var(--border);background:#101018}
.chat-search{width:100%;border:1px solid #303044;border-radius:999px;padding:10px 14px;background:#20202d;color:var(--text);outline:none;font-size:.88rem}
.chat-search:focus{border-color:var(--gold);box-shadow:0 0 0 3px rgba(212,175,55,.1)}
.chat-list-caption{padding:8px 14px 2px;color:var(--soft);font-size:.72rem;text-transform:uppercase;letter-spacing:.06em}
.chat-contact-row{display:flex;align-items:center;gap:11px;padding:11px 13px;border-bottom:1px solid rgba(40,40,56,.75);cursor:pointer;transition:background .15s}
.chat-contact-row:hover{background:rgba(212,175,55,.08)}
.chat-contact-row.unread{background:rgba(212,175,55,.08)}
.chat-contact-avatar{width:44px;height:44px;flex:0 0 44px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#38384d,#181824);border:1px solid #3b3b4d;overflow:hidden;font-weight:800;color:#f5d66c}
.chat-contact-avatar img{width:100%;height:100%;object-fit:cover}
.chat-contact-main{min-width:0;flex:1}
.chat-contact-top{display:flex;align-items:center;justify-content:space-between;gap:6px}
.chat-contact-name{font-size:.9rem;font-weight:750;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chat-contact-time{font-size:.68rem;color:var(--soft);white-space:nowrap}
.chat-contact-preview{font-size:.78rem;color:var(--soft);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:2px}
.chat-unread-dot{width:9px;height:9px;border-radius:50%;background:#3b82f6;flex:0 0 9px}
.chat-header-user{display:flex;align-items:center;gap:10px;min-width:0}
.chat-header-avatar{width:40px;height:40px;flex:0 0 40px;border-radius:50%;background:#2b2b3b;overflow:hidden;display:flex;align-items:center;justify-content:center;font-weight:800;color:#f0d36c}
.chat-header-avatar img{width:100%;height:100%;object-fit:cover}
.chat-header-copy{min-width:0}
.chat-header-copy .panel-title{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chat-subtitle{font-size:.7rem;color:var(--soft)}
.msg-day-divider{text-align:center;color:var(--soft);font-size:.72rem;margin:8px 0}
.msg-receipt{font-size:.68rem;color:#b5b5c5;text-align:right;margin-top:2px}
.msg-me .msg-time{color:rgba(20,17,8,.7)}
@media(max-width:520px){.chat-overlay{padding:12px 8px 86px}.chat-window{height:min(78vh,650px);width:calc(100vw - 16px)}.chat-launcher{right:15px;bottom:15px}.chat-wrap .dropdown-panel{right:8px;bottom:82px}}

.container{max-width:1200px;margin:0 auto;padding:24px 20px}
.sectitle{font-size:1.3rem;font-weight:800;margin:28px 0 16px;padding-bottom:8px;border-bottom:1px solid var(--border)}
.alert-block{background:linear-gradient(90deg,rgba(196,30,58,.08),rgba(212,175,55,.05));border:1px solid rgba(212,175,55,.3);border-radius:var(--r);padding:20px;margin-bottom:30px}
.alert-block h3{color:var(--gold);margin-bottom:10px}
.alert-block ol{padding-left:20px;margin:8px 0}
.warn{color:#ff6b66;margin-top:10px;font-weight:600}
.catnav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}
.cattab{padding:9px 16px;background:var(--card);border:1px solid var(--border);color:var(--soft);border-radius:var(--r);cursor:pointer;font-weight:600;transition:.2s}
.cattab.active{border-color:var(--gold);color:var(--gold);background:rgba(212,175,55,.1)}
.postcard{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:20px;margin-bottom:14px;transition:.25s}
.postcard:hover{border-color:var(--gold);transform:translateY(-2px)}
.post-header{display:flex;align-items:center;gap:12px;margin-bottom:10px}
.avatar-wrap{width:42px;height:42px;border-radius:50%;padding:3px}
.avatar-wrap.admin{background:linear-gradient(135deg,#ffd700,#ffed4e,#ffd700)}
.avatar-wrap.vip{background:linear-gradient(135deg,#9932cc,#da70d6,#9932cc)}
.avatar-wrap.member{background:linear-gradient(135deg,#4b5563,#6b7280,#4b5563)}
.avatar-img{width:100%;height:100%;border-radius:50%;object-fit:cover;border:2px solid #000}
.avatar-placeholder{width:100%;height:100%;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#1f2937;font-size:1.1rem;border:2px solid #000}
.post-title{font-size:1.1rem;margin-bottom:8px}
.post-meta-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.role-badge{font-size:.7rem;padding:2px 8px;border-radius:10px;font-weight:700}
.post-desc{color:#bbb;white-space:pre-line;margin-bottom:12px}
.post-imgs{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;margin:12px 0}
.post-imgs img{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:var(--r);cursor:pointer;border:1px solid var(--border);transition:.2s}
.post-imgs img:hover{transform:scale(1.03)}
.post-foot{display:flex;justify-content:space-between;align-items:center;margin-top:14px;padding-top:14px;border-top:1px solid var(--border);font-size:.85rem;color:var(--soft)}
.chat-btn-post{background:var(--blue);color:#fff;border:none;padding:8px 14px;border-radius:var(--r);font-weight:700}
.del-btn{background:var(--red);color:#fff;border:none;padding:6px 10px;border-radius:8px;font-size:.8rem}
.form-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:24px;max-width:640px;margin:0 auto 30px}
.form-card h3{color:var(--gold);margin-bottom:20px}
.form-group{margin-bottom:16px}
.form-group label{display:block;margin-bottom:6px;font-size:.9rem;color:var(--soft)}
.form-input,select,textarea{width:100%;padding:12px 16px;background:#0a0a10;border:1px solid var(--border);border-radius:var(--r);color:var(--text);font-size:1rem}
.form-input:focus,select:focus,textarea:focus{outline:none;border-color:var(--gold)}
.upload-area{border:2px dashed var(--border);border-radius:var(--r);padding:20px;text-align:center;margin:16px 0;transition:.2s;cursor:pointer}
.upload-area:hover{border-color:var(--gold)}
.preview-row{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
.preview-item{position:relative;width:90px;height:90px}
.preview-item img{width:100%;height:100%;object-fit:cover;border-radius:var(--r)}
.preview-del{position:absolute;top:4px;right:4px;background:rgba(0,0,0,.7);color:#fff;border:none;width:24px;height:24px;border-radius:50%;font-size:1rem;display:flex;align-items:center;justify-content:center;cursor:pointer}
.content-tab{display:none}
.content-tab.active{display:block;animation:fadeIn .3s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.profile-card{max-width:500px;margin:0 auto}
.profile-avatar-row{display:flex;align-items:center;gap:20px;margin-bottom:24px}
.profile-avatar-frame{width:100px;height:100px;border-radius:50%;padding:4px;cursor:pointer}
.profile-avatar-frame.admin{background:linear-gradient(135deg,#ffd700,#ffed4e,#ffd700)}
.profile-avatar-frame.vip{background:linear-gradient(135deg,#9932cc,#da70d6,#9932cc)}
.profile-avatar-frame.member{background:linear-gradient(135deg,#4b5563,#6b7280,#4b5563)}
.profile-avatar-img{width:100%;height:100%;border-radius:50%;object-fit:cover;border:3px solid #000}
.profile-avatar-placeholder{width:100%;height:100%;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#1f2937;font-size:2rem;border:3px solid #000}
.profile-info h2{font-size:1.4rem;margin-bottom:4px}
.profile-role{display:inline-block;padding:4px 12px;border-radius:12px;font-weight:700;font-size:.85rem;margin-bottom:10px}
.profile-role.admin{background:linear-gradient(90deg,#b8860b,#ffd700);color:#000}
.profile-role.vip{background:linear-gradient(90deg,#8b00ff,#da70d6);color:#fff}
.profile-role.member{background:linear-gradient(90deg,#374151,#6b7280);color:#fff}
.profile-bio{color:#ccc;white-space:pre-line;margin-bottom:10px}
.profile-meta{font-size:.8rem;color:var(--soft)}
.profile-link{background:none;border:0;color:var(--gold);font:inherit;font-weight:700;text-decoration:underline;cursor:pointer;padding:0}
.public-profile-overlay{display:none;position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.78);align-items:center;justify-content:center;padding:18px}
.public-profile-overlay.show{display:flex}
.public-profile-card{width:min(100%,480px);background:var(--card);border:1px solid var(--border);border-radius:16px;padding:24px;position:relative}
.public-profile-close{position:absolute;right:14px;top:10px;background:transparent;border:0;color:var(--text);font-size:1.6rem;cursor:pointer}
.public-profile-bio{white-space:pre-wrap;color:var(--soft);margin-top:14px;overflow-wrap:anywhere}

.admin-role-section{margin-top:20px;padding-top:20px;border-top:1px dashed var(--border)}
.hidden-input{display:none}
</style>
</head>
<body>
<header>
  <div class="head">
    <div class="brand" onclick="showTab('market')"><span>FM</span>_Market</div>
    <nav class="nav">
      <button class="btn btn-sm btn-ghost" onclick="showTab('market')">📋 ตลาด</button>
      <button class="btn btn-sm btn-gold" onclick="showTab('post')">✍️ โพสต์</button>
      <div class="notif-wrap">
        <button class="bell-btn" onclick="toggleNotif()">🔔<span id="notifBadge" class="badge-count">0</span></button>
        <div id="notifPanel" class="dropdown-panel">
          <div class="panel-head">
            <span class="panel-title">🔔 การแจ้งเตือน</span>
            <div class="panel-actions">
              <button onclick="markAllNotifRead()">อ่านทั้งหมด</button>
            </div>
          </div>
          <div id="notifList" class="panel-list"><div class="empty-state">กำลังโหลด...</div></div>
        </div>
      </div>
      <div class="chat-wrap">
        <button class="bell-btn" onclick="toggleChatList()">💬<span id="chatBadge" class="badge-count">0</span></button>
        <div id="chatListPanel" class="dropdown-panel">
          <div class="panel-head">
            <span class="panel-title">💬 Messenger</span>
            <div class="panel-actions"><button type="button" onclick="clearChatSearch()">แชทล่าสุด</button></div>
          </div>
          <div class="chat-search-wrap">
            <input id="chatSearch" class="chat-search" type="search" placeholder="ค้นหาสมาชิกเพื่อเริ่มแชท..." autocomplete="off" oninput="searchChatUsers()" aria-label="ค้นหาสมาชิกสำหรับแชท">
          </div>
          <div id="chatListBody" class="panel-list"><div class="empty-state">กำลังโหลด...</div></div>
        </div>
      </div>
      <div class="profile-wrap">
        <button class="profile-btn" onclick="showTab('profile')">👤 {{ session_user.username }}</button>
      </div>
      {% if session_user.role == 'admin' %}
      <span class="badge badge-admin">ผู้ดูแล</span>
      {% elif session_user.role == 'vip' %}
      <span class="badge" style="background:linear-gradient(90deg,#8b00ff,#da70d6);color:#fff">VIP</span>
      {% else %}
      <span class="badge badge-member">สมาชิก</span>
      {% endif %}
      <button class="btn btn-sm btn-red" onclick="doLogout()">ออก</button>
    </nav>
  </div>
</header>

<button class="chat-launcher" type="button" onclick="toggleChatList()" aria-label="เปิดแชท" title="เปิดแชท">💬</button>
<div id="chatOverlay" class="chat-overlay">
  <div class="chat-window" onclick="event.stopPropagation()">
    <div class="chat-header">
      <div class="chat-header-user">
        <div id="chatPartnerAvatar" class="chat-header-avatar">👤</div>
        <div class="chat-header-copy"><div id="chatPartnerName" class="panel-title">แชท</div><div id="chatPartnerSubtitle" class="chat-subtitle">FM_Market Messenger · บันทึกประวัติอัตโนมัติ</div></div>
      </div>
      <button class="chat-close" onclick="closeChat()" aria-label="ปิดแชท">×</button>
    </div>
    <div id="mediationControls" class="mediation-controls">
      <button id="inviteAdminBtn" class="mediation-invite-btn" type="button" onclick="inviteMediator()">🛡️ เชิญแอดมินเป็นคนกลาง</button>
      <button id="endSaleBtn" class="mediation-end-btn" type="button" onclick="endMediatedSale()" hidden>✓ จบการขาย</button>
      <button id="leaveMediationBtn" class="mediation-leave-btn" type="button" onclick="leaveMediationRoom()" hidden>กลับไปแชทส่วนตัว</button>
      <div id="mediationInfo" class="mediation-info" hidden></div>
    </div>
    <div id="chatMessages" class="chat-messages"><div class="empty-state">เลือกผู้ติดต่อเพื่อเริ่มแชท</div></div>
    <div id="emojiPicker" class="emoji-picker" aria-label="เลือกอีโมจิ"></div>
    <div id="gifPanel" class="gif-panel">
      <input type="url" id="gifUrlInput" placeholder="วางลิงก์ GIF จาก Tenor / GIPHY">
      <button class="chat-send-btn" type="button" onclick="sendGifMessage()">ส่ง GIF</button>
      <button class="btn btn-sm btn-ghost" type="button" onclick="searchGif()">ค้นหา</button>
      <div class="gif-help">ใช้ลิงก์ไฟล์ GIF โดยตรงจาก media.tenor.com หรือ media.giphy.com</div>
    </div>
    <div class="chat-input-area">
      <button class="chat-tool-btn" type="button" title="อีโมจิ" onclick="toggleEmojiPicker()">😊</button>
      <button class="chat-tool-btn" type="button" title="ส่ง GIF" onclick="toggleGifPanel()">GIF</button>
      <input type="text" id="chatInput" placeholder="พิมพ์ข้อความ..." onkeydown="onChatEnter(event)" autocomplete="off">
      <button class="chat-send-btn" onclick="sendChatMessage()">ส่ง</button>
    </div>
  </div>
</div>

<div id="publicProfileOverlay" class="public-profile-overlay" role="dialog" aria-modal="true" aria-labelledby="publicProfileName" onclick="if(event.target===this)closePublicProfile()">
  <div class="public-profile-card">
    <button class="public-profile-close" type="button" aria-label="ปิด" onclick="closePublicProfile()">×</button>
    <div id="publicProfileBanner" style="height:110px;border-radius:12px;background:linear-gradient(120deg,#202020,#4b3b14);margin:0 0 18px;background-size:cover;background-position:center"></div>
    <div class="profile-avatar-row">
      <div id="publicProfileAvatar" class="profile-avatar-frame member"><div class="profile-avatar-placeholder">👤</div></div>
      <div class="profile-info"><h2 id="publicProfileName">โปรไฟล์สมาชิก</h2><span id="publicProfileRole" class="profile-role member">สมาชิกทั่วไป</span><div id="publicProfileCreated" class="profile-meta"></div></div>
    </div>
    <h4>แนะนำตัว</h4><div id="publicProfileBio" class="public-profile-bio">ยังไม่ได้แนะนำตัว</div>
    <div style="margin-top:22px"><button id="publicProfileChat" class="btn btn-blue" type="button">💬 ส่งข้อความ</button></div>
  </div>
</div>

<main class="container">
  <div id="tabMarket" class="content-tab active">
    <h2 class="sectitle">📢 ประกาศจากระบบ</h2>
    {% for n in news %}
    <div class="postcard">
      <div style="font-size:.8rem;color:var(--soft);margin-bottom:6px">{{ n.date }}</div>
      <h4 style="margin-bottom:6px">{{ n.title }}</h4>
      <p style="color:var(--soft)">{{ n.content }}</p>
    </div>
    {% endfor %}
    <section class="alert-block">
      <h3>🛡️ วิธีใช้งานอย่างปลอดภัย</h3>
      <ol>
        <li>ตกลงรายละเอียดผ่านแชทในระบบเท่านั้น</li>
        <li>โอนเงินผ่านบัญชีกลางของแอดมิน</li>
        <li>แจ้งหลักฐาน → แอดมินยืนยันการทำรายการ</li>
        <li>ผู้ขายส่งของ → ผู้ซื้อตรวจสอบ → ระบบจ่ายเงินให้ผู้ขาย</li>
      </ol>
      <p class="warn">⚠️ ห้ามโอนเงินให้ผู้อื่นโดยตรง — เราไม่รับผิดชอบหากไม่ทำตาม</p>
    </section>
    <h2 class="sectitle">📋 รายการซื้อขาย</h2>
    <div class="catnav">
      <button class="cattab active" data-cat="all" onclick="filterCat('all')">ทั้งหมด</button>
      {% for k,v in categories.items() %}
      <button class="cattab" data-cat="{{k}}" onclick="filterCat('{{k}}')">{{v.icon}} {{v.name}}</button>
      {% endfor %}
    </div>
    <div id="postList">
      {% if posts %}
      {% for p in posts %}
      {% set author_data = all_users.get(p.author, {'role': 'member', 'avatar': none}) %}
      {% set role_info = get_role_config(author_data.get('role', 'member')) %}
      <div class="postcard" data-cat="{{p.category}}">
        <div class="post-header">
          <div class="avatar-wrap {{author_data.role}}">
            {% if author_data.avatar %}
            <img src="{{author_data.avatar}}" class="avatar-img" alt="">
            {% else %}
            <div class="avatar-placeholder">{{p.author[0]|upper}}</div>
            {% endif %}
          </div>
          <div style="flex:1">
            <div class="post-title">{{ p.title }}</div>
            <div class="post-meta-row">
              <span>{{role_info.badge}} <button class="profile-link" type="button" onclick="openPublicProfile({{ p.author|tojson }})">{{p.author}}</button></span>
              <span class="role-badge" style="background:{{role_info.bg_badge}};color:#fff">{{role_info.name}}</span>
              <span style="color:var(--soft)">{{ p.time }}</span>
            </div>
          </div>
          {% if p.author == session_user.username or session_user.role == 'admin' %}
          <button class="del-btn" onclick="delPost('{{p.id}}')">ลบ</button>
          {% endif %}
        </div>
        <p class="post-desc">{{ p.detail }}</p>
        {% if p.images %}
        <div class="post-imgs">
          {% for img in p.images %}
          <img src="{{img}}" alt="" onclick="window.open('{{img}}')">
          {% endfor %}
        </div>
        {% endif %}
        <div class="post-foot">
          <span>👤 <button class="profile-link" type="button" onclick="openPublicProfile({{ p.author|tojson }})">{{ p.author }}</button></span>
          <span>{{ p.time }}</span>
          <button class="chat-btn-post" onclick="openChatWith({{ p.author|tojson }})">💬 คุยด้วย</button>
        </div>
      </div>
      {% endfor %}
      {% else %}
      <div class="empty-state">ยังไม่มีรายการ — เป็นคนแรกที่ลงประกาศเลย!</div>
      {% endif %}
    </div>
  </div>

  <div id="tabPost" class="content-tab">
    <div class="form-card">
      <h3>✍️ ลงประกาศสินค้า</h3>
      <form id="postForm" onsubmit="submitPost(event)">
        <div class="form-group">
          <label>หมวดหมู่</label>
          <select id="category" class="form-input">
            {% for k,v in categories.items() %}
            <option value="{{k}}">{{v.icon}} {{v.name}}</option>
            {% endfor %}
          </select>
        </div>
        <div class="form-group">
          <label>หัวข้อ *</label>
          <input type="text" id="title" class="form-input" placeholder="เช่น ขายเงิน M ราคาถูก" required>
        </div>
        <div class="form-group">
          <label>รายละเอียด</label>
          <textarea id="detail" class="form-input" rows="4" placeholder="เช่น ราคา 100 บาท ต่อ 1M..."></textarea>
        </div>
        <div class="form-group">
          <label>รูปภาพ (สูงสุด 5 รูป)</label>
          <div class="upload-area" onclick="document.getElementById('imgUpload').click()">
            📷 คลิกเพื่ออัปโหลดรูป
          </div>
          <input type="file" id="imgUpload" accept="image/*" multiple class="hidden-input" onchange="handleImgUpload(this.files)">
          <div id="imgPreviewRow" class="preview-row"></div>
        </div>
        <button type="submit" class="btn btn-gold" style="
padding:12px 24px;width:100%">ลงประกาศ</button>
      </form>
    </div>
  </div>

  <div id="tabProfile" class="content-tab">
    <div class="form-card profile-card">
      <h3>👤 โปรไฟล์ของฉัน</h3>
      <div id="myProfileBanner" style="height:110px;border-radius:12px;background:linear-gradient(120deg,#202020,#4b3b14);margin:0 0 18px;background-size:cover;background-position:center"></div>
      <div class="profile-avatar-row">
        <div id="profileAvatar" class="profile-avatar-frame member" onclick="document.getElementById('avatarUpload').click()">
          <div class="profile-avatar-placeholder">👤</div>
        </div>
        <div class="profile-info">
          <h2 id="profileUsername">{{ session_user.username }}</h2>
          <span id="profileRole" class="profile-role member">สมาชิกทั่วไป</span>
          <div id="profileCreated" class="profile-meta"></div>
        </div>
      </div>
      <input id="avatarUpload" class="hidden-input" type="file" accept="image/png,image/jpeg,image/gif,image/webp" onchange="uploadAvatar(this.files[0])">
      <div class="form-group">
        <label for="profileTheme">สีธีมโปรไฟล์</label>
        <input id="profileTheme" type="color" class="form-input" value="#d4af37" style="height:48px;padding:4px;max-width:100px">
      </div>
      <div class="form-group">
        <label for="profileBio">แนะนำตัว (เขียนได้หลายบรรทัด)</label>
        <textarea id="profileBio" class="form-input" rows="4" maxlength="500" placeholder="เขียนแนะนำตัว..."></textarea>
      </div>
      <button class="btn btn-gold" onclick="saveProfile()">บันทึกโปรไฟล์</button>
      {% if session_user.role == 'admin' %}
      <div class="admin-role-section">
        <h3>👑 จัดการยศสมาชิก</h3>
        <div class="form-group"><label>ชื่อผู้ใช้</label><input id="roleUsername" class="form-input" placeholder="ชื่อสมาชิก"></div>
        <div class="form-group"><label>ยศ</label><select id="roleValue" class="form-input"><option value="member">สมาชิกทั่วไป</option><option value="vip">VIP</option><option value="admin">ผู้ดูแลระบบ</option></select></div>
        <button class="btn btn-blue" onclick="setUserRole()">เปลี่ยนยศ</button>
      </div>
      {% endif %}
    </div>
  </div>
</main>

<script>
let uploadedImages = [];
let currentPartner = null;
let currentMediationId = null;
let currentMediationAdmin = false;
let presenceBusy = false;
const currentUsername = {{ session_user.username|tojson }};

function showTab(tab) {
  document.querySelectorAll('.content-tab').forEach(el => el.classList.remove('active'));
  const target = document.getElementById('tab' + tab.charAt(0).toUpperCase() + tab.slice(1));
  if (target) target.classList.add('active');
  if (tab === 'profile') loadProfile();
}
function filterCat(cat) {
  document.querySelectorAll('.cattab').forEach(b => b.classList.toggle('active', b.dataset.cat === cat));
  document.querySelectorAll('#postList .postcard[data-cat]').forEach(p => p.style.display = (cat === 'all' || p.dataset.cat === cat) ? '' : 'none');
}
async function api(url, options={}) {
  const response = await fetch(url, options);
  let data;
  try { data = await response.json(); } catch (_) { throw new Error('เซิร์ฟเวอร์ตอบกลับไม่ถูกต้อง'); }
  if (!response.ok) throw new Error(data.message || 'เกิดข้อผิดพลาด');
  return data;
}
async function submitPost(e) {
  e.preventDefault();
  try {
    const d = await api('/api/post', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({category:document.getElementById('category').value,title:document.getElementById('title').value,detail:document.getElementById('detail').value,images:uploadedImages})});
    if (!d.success) throw new Error(d.message || 'ลงประกาศไม่สำเร็จ');
    alert('ลงประกาศสำเร็จ'); location.reload();
  } catch (err) { alert(err.message); }
}
async function handleImgUpload(files) {
  for (const file of Array.from(files)) {
    if (uploadedImages.length >= 5) { alert('อัปโหลดได้สูงสุด 5 รูป'); break; }
    if (!file.type.startsWith('image/')) { alert('กรุณาเลือกไฟล์รูปภาพ'); continue; }
    const form = new FormData(); form.append('image', file);
    try {
      const d = await api('/api/upload-image', {method:'POST',body:form});
      if (d.success) { uploadedImages.push(d.url); renderImagePreviews(); }
      else alert(d.message || 'อัปโหลดไม่สำเร็จ');
    } catch (err) { alert(err.message); }
  }
  document.getElementById('imgUpload').value = '';
}
function renderImagePreviews() {
  const row = document.getElementById('imgPreviewRow'); row.replaceChildren();
  uploadedImages.forEach((url, i) => {
    const wrap = document.createElement('div'); wrap.className = 'preview-item';
    const img = document.createElement('img'); img.src = url; img.alt = 'ตัวอย่างรูป';
    const btn = document.createElement('button'); btn.type='button'; btn.className='preview-del'; btn.textContent='×'; btn.onclick=()=>{uploadedImages.splice(i,1);renderImagePreviews();};
    wrap.append(img,btn); row.append(wrap);
  });
}
async function delPost(id) {
  if (!confirm('ยืนยันลบประกาศนี้?')) return;
  try { const d = await api('/api/post/'+encodeURIComponent(id),{method:'DELETE'}); if(!d.success) throw new Error(d.message || 'ลบไม่สำเร็จ'); location.reload(); }
  catch(err){alert(err.message);}
}
async function doLogout() {
  try { await api('/api/logout'); location.href='/'; } catch(err){alert(err.message);}
}
async function openPublicProfile(username) {
  try {
    const d = await api('/api/profile/' + encodeURIComponent(username));
    if (!d.success) throw new Error(d.message || 'เปิดโปรไฟล์ไม่สำเร็จ');
    document.getElementById('publicProfileName').textContent = d.username;
    document.getElementById('publicProfileCreated').textContent = 'สมัครเมื่อ ' + (d.created_at || '-');
    document.getElementById('publicProfileBio').textContent = d.bio || 'ยังไม่ได้แนะนำตัว';
    const banner=document.getElementById('publicProfileBanner'); banner.style.backgroundColor=d.profile_theme||'#d4af37'; banner.style.backgroundImage=d.profile_banner ? `url('${d.profile_banner}')` : `linear-gradient(120deg,${d.profile_theme||'#d4af37'},#171717)`; document.querySelector('.public-profile-card').style.setProperty('--profile-accent',d.profile_theme||'#d4af37');
    const role = document.getElementById('publicProfileRole');
    role.textContent = d.role_info.name; role.className = 'profile-role ' + d.role;
    const frame = document.getElementById('publicProfileAvatar');
    frame.className = 'profile-avatar-frame ' + d.role; frame.replaceChildren();
    if (d.avatar) { const img = document.createElement('img'); img.src = d.avatar; img.className = 'profile-avatar-img'; img.alt = 'รูปโปรไฟล์'; frame.append(img); }
    else { const placeholder = document.createElement('div'); placeholder.className = 'profile-avatar-placeholder'; placeholder.textContent = (d.username[0] || '?').toUpperCase(); frame.append(placeholder); }
    const chat = document.getElementById('publicProfileChat');
    chat.style.display = d.username === currentUsername ? 'none' : '';
    chat.onclick = () => { closePublicProfile(); openChatWith(d.username); };
    document.getElementById('publicProfileOverlay').classList.add('show');
  } catch (err) { alert(err.message); }
}
function closePublicProfile() { document.getElementById('publicProfileOverlay').classList.remove('show'); }
document.addEventListener('keydown', e => { if (e.key === 'Escape') closePublicProfile(); });

async function loadProfile() {
  try {
    const d = await api('/api/profile'); if(!d.success) return;
    document.getElementById('profileUsername').textContent=d.username;
    document.getElementById('profileBio').value=d.bio || '';
    document.getElementById('profileTheme').value=d.profile_theme || '#d4af37';
    const banner=document.getElementById('myProfileBanner'); banner.style.backgroundImage=d.profile_banner ? `url('${d.profile_banner}')` : `linear-gradient(120deg,${d.profile_theme||'#d4af37'},#171717)`;
    document.getElementById('profileCreated').textContent='สมัครเมื่อ '+(d.created_at || '-');
    const role = document.getElementById('profileRole'); role.textContent=d.role_info.name; role.className='profile-role '+d.role;
    const frame=document.getElementById('profileAvatar'); frame.className='profile-avatar-frame '+d.role;
    frame.replaceChildren();
    if(d.avatar){const img=document.createElement('img');img.src=d.avatar;img.className='profile-avatar-img';img.alt='รูปโปรไฟล์';frame.append(img);}
    else {const placeholder=document.createElement('div');placeholder.className='profile-avatar-placeholder';placeholder.textContent=(d.username[0]||'?').toUpperCase();frame.append(placeholder);}
  } catch(err){console.error(err);}
}
async function saveProfile() {
  try { const d=await api('/api/profile/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bio:document.getElementById('profileBio').value,profile_theme:document.getElementById('profileTheme').value})}); alert(d.message || 'บันทึกแล้ว'); }
  catch(err){alert(err.message);}
}
async function uploadAvatar(file) {
  if(!file) return;
  const form=new FormData();form.append('avatar',file);
  try {const d=await api('/api/upload-avatar',{method:'POST',body:form});if(!d.success)throw new Error(d.message||'อัปโหลดไม่สำเร็จ');await loadProfile();alert('เปลี่ยนรูปโปรไฟล์แล้ว');}
  catch(err){alert(err.message);} finally {document.getElementById('avatarUpload').value='';}
}
async function setUserRole() {
  try {const d=await api('/api/admin/set-role',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:document.getElementById('roleUsername').value,role:document.getElementById('roleValue').value})});alert(d.message || (d.success?'เปลี่ยนยศสำเร็จ':'ทำรายการไม่สำเร็จ'));}
  catch(err){alert(err.message);}
}
function toggleNotif(){document.getElementById('notifPanel').classList.toggle('show');loadNotifications();}
function toggleChatList(){document.getElementById('chatListPanel').classList.toggle('show');loadChatOverview();}
// Render stored server timestamps (DD/MM/YYYY HH:mm) as friendly Thai time.
// Render runs in UTC, so interpret the stored value as UTC and display Asia/Bangkok.
function parseNotificationTime(raw){
  const match=/^(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{1,2}):(\d{2})$/.exec(String(raw||'').trim());
  if(!match)return null;
  const [,dd,mm,yyyy,hh,min]=match;
  const date=new Date(Date.UTC(Number(yyyy),Number(mm)-1,Number(dd),Number(hh),Number(min)));
  return Number.isNaN(date.getTime())?null:date;
}
function formatNotificationTime(raw){
  const date=parseNotificationTime(raw);
  if(!date)return 'เวลาไม่พร้อมใช้งาน';
  const now=Date.now();
  const diff=Math.max(0,now-date.getTime());
  const bangkokDate=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Bangkok',year:'numeric',month:'2-digit',day:'2-digit'});
  const bangkokClock=new Intl.DateTimeFormat('th-TH',{timeZone:'Asia/Bangkok',hour:'2-digit',minute:'2-digit',hour12:false});
  const clock=bangkokClock.format(date);
  if(diff<60*1000)return 'เมื่อสักครู่';
  if(diff<60*60*1000)return Math.floor(diff/60000)+' นาทีที่แล้ว';
  if(diff<24*60*60*1000 && bangkokDate.format(date)===bangkokDate.format(new Date()))return Math.floor(diff/3600000)+' ชั่วโมงที่แล้ว';
  const today=bangkokDate.format(new Date());
  const yesterday=bangkokDate.format(new Date(now-24*60*60*1000));
  if(bangkokDate.format(date)===today)return 'วันนี้ เวลา '+clock;
  if(bangkokDate.format(date)===yesterday)return 'เมื่อวาน เวลา '+clock;
  return new Intl.DateTimeFormat('th-TH',{timeZone:'Asia/Bangkok',day:'numeric',month:'short',year:'numeric'}).format(date)+' • '+clock;
}
async function loadNotifications(){
  try {
    const d=await api('/api/notifications');
    const list=document.getElementById('notifList');
    list.replaceChildren();
    const badge=document.getElementById('notifBadge');
    badge.textContent=d.unread_count;
    badge.classList.toggle('show',d.unread_count>0);
    if(!d.notifications.length){list.innerHTML='<div class="empty-state">ไม่มีการแจ้งเตือน</div>';return;}
    [...d.notifications].reverse().forEach(n=>{
      const el=document.createElement('div');
      el.className='panel-item'+(!n.read?' unread':'');
      const name=document.createElement('div');
      name.className='panel-item-name';
      name.textContent=n.type==='message'?'💬 ข้อความใหม่':'แจ้งเตือน';
      const body=document.createElement('div');
      body.className='panel-item-text';
      body.textContent=n.text;
      const time=document.createElement('div');
      time.className='panel-item-time';
      time.textContent=formatNotificationTime(n.time);
      time.title=parseNotificationTime(n.time)?'เวลาประเทศไทย: '+new Intl.DateTimeFormat('th-TH',{timeZone:'Asia/Bangkok',dateStyle:'medium',timeStyle:'short'}).format(parseNotificationTime(n.time)):'ไม่พบเวลาที่บันทึกไว้';
      el.append(name,body,time);
      if(n.type==='message'&&n.from&&n.from!==currentUsername){
        el.title='คลิกเพื่อเปิดแชท';
        el.onclick=()=>{document.getElementById('notifPanel').classList.remove('show');openChatWith(n.from);};
      }
      list.append(el);
    });
  }catch(err){console.error(err);}
}
async function markAllNotifRead(){try{await api('/api/notifications/mark-read',{method:'POST'});loadNotifications();}catch(err){alert(err.message);}}
function chatAvatarNode(avatar, username, className='chat-contact-avatar'){
  const node=document.createElement('div');node.className=className;
  if(avatar){const img=document.createElement('img');img.src=avatar;img.alt='';img.loading='lazy';img.onerror=()=>{node.textContent=(username||'?').slice(0,1).toUpperCase();};node.append(img);}
  else node.textContent=(username||'?').slice(0,1).toUpperCase();
  return node;
}
function chatTimeLabel(raw){
  const d=parseNotificationTime(raw);
  if(!d)return '';
  return new Intl.DateTimeFormat('th-TH',{timeZone:'Asia/Bangkok',hour:'2-digit',minute:'2-digit',hour12:false}).format(d);
}
function renderChatContact({username,avatar,last_msg='',time='',unread=0,role='member',isSearch=false}){
  const row=document.createElement('div');row.className='chat-contact-row'+(unread?' unread':'');row.tabIndex=0;row.setAttribute('role','button');row.setAttribute('aria-label','เปิดแชทกับ '+username);
  row.append(chatAvatarNode(avatar,username));
  const main=document.createElement('div');main.className='chat-contact-main';
  const top=document.createElement('div');top.className='chat-contact-top';
  const name=document.createElement('div');name.className='chat-contact-name';name.textContent=username;
  const timeNode=document.createElement('div');timeNode.className='chat-contact-time';timeNode.textContent=isSearch?(role==='admin'?'ผู้ดูแลระบบ':role==='vip'?'VIP':'สมาชิก'):formatNotificationTime(time);
  top.append(name,timeNode);
  const preview=document.createElement('div');preview.className='chat-contact-preview';preview.textContent=isSearch?(last_msg||'เริ่มบทสนทนาใหม่'):((last_msg||'เริ่มคุยกัน').slice(0,100));
  main.append(top,preview);row.append(main);
  if(unread){const dot=document.createElement('span');dot.className='chat-unread-dot';dot.title='มีข้อความที่ยังไม่ได้อ่าน';row.append(dot);}
  const open=()=>{document.getElementById('chatListPanel').classList.remove('show');openChatWith(username,avatar);};row.onclick=open;row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}};
  return row;
}
async function loadChatOverview(){
  try{
    const d=await api('/api/chat-overview');
    const body=document.getElementById('chatListBody');if(!body)return;
    const search=document.getElementById('chatSearch');if(search&&search.value.trim())return;
    body.replaceChildren();
    const badge=document.getElementById('chatBadge');badge.textContent=d.total_unread||0;badge.classList.toggle('show',(d.total_unread||0)>0);
    const contacts=Object.entries(d.contacts||{}).sort((a,b)=>{
      const ad=parseNotificationTime(a[1].time)?.getTime()||0;const bd=parseNotificationTime(b[1].time)?.getTime()||0;return bd-ad;
    });
    if(!contacts.length){const empty=document.createElement('div');empty.className='empty-state';empty.textContent='ยังไม่มีแชท — ค้นหาสมาชิกด้านบนเพื่อเริ่มคุย';body.append(empty);return;}
    const cap=document.createElement('div');cap.className='chat-list-caption';cap.textContent='บทสนทนาล่าสุด';body.append(cap);
    contacts.forEach(([username,c])=>body.append(renderChatContact({username,avatar:c.avatar,last_msg:c.last_msg,time:c.time,unread:c.unread,role:c.role})));
  }catch(err){console.error(err);}
}
let chatSearchRequest=0;
async function searchChatUsers(){
  const input=document.getElementById('chatSearch');const q=input.value.trim();
  if(!q){await loadChatOverview();return;}
  const requestId=++chatSearchRequest;const body=document.getElementById('chatListBody');body.replaceChildren();
  const loading=document.createElement('div');loading.className='empty-state';loading.textContent='กำลังค้นหาสมาชิก...';body.append(loading);
  try{
    const d=await api('/api/chat-users?q='+encodeURIComponent(q));if(requestId!==chatSearchRequest)return;
    body.replaceChildren();const users=d.users||[];
    if(!users.length){const empty=document.createElement('div');empty.className='empty-state';empty.textContent='ไม่พบสมาชิกที่ตรงกับคำค้น';body.append(empty);return;}
    const cap=document.createElement('div');cap.className='chat-list-caption';cap.textContent='สมาชิกที่ค้นพบ';body.append(cap);
    users.forEach(u=>body.append(renderChatContact({username:u.username,avatar:u.avatar,role:u.role,last_msg:u.bio||'เริ่มบทสนทนาใหม่',isSearch:true})));
  }catch(err){if(requestId!==chatSearchRequest)return;body.replaceChildren();const empty=document.createElement('div');empty.className='empty-state';empty.textContent=err.message||'ค้นหาสมาชิกไม่สำเร็จ';body.append(empty);}
}
function clearChatSearch(){const input=document.getElementById('chatSearch');if(input)input.value='';chatSearchRequest++;loadChatOverview();}
async function markAllChatRead(){try{const d=await api('/api/chat-overview');for(const name of Object.keys(d.contacts||{})){await api('/api/conversation/'+encodeURIComponent(name)+'/read',{method:'POST'});}await loadChatOverview();}catch(err){alert(err.message);}}
function setMediationControls(mode, room=null){
  const invite=document.getElementById('inviteAdminBtn');
  const end=document.getElementById('endSaleBtn');
  const leave=document.getElementById('leaveMediationBtn');
  const info=document.getElementById('mediationInfo');
  invite.hidden=mode!=='private';
  end.hidden=mode!=='room'||!currentMediationAdmin;
  leave.hidden=mode!=='room';
  info.hidden=mode!=='room';
  if(room&&mode==='room') info.textContent='ห้องคนกลาง · แอดมิน '+room.admin+' · ผู้ซื้อ/ผู้ขาย: '+(room.pair||[]).join(' และ ')+' · ห้องจะปิดได้เมื่อแอดมินกด “จบการขาย”';
  if(mode==='private') info.textContent='';
}
async function inviteMediator(){
  if(!currentPartner||currentMediationId){alert('กรุณาเปิดแชทส่วนตัวกับผู้ซื้อหรือผู้ขายก่อน');return;}
  const btn=document.getElementById('inviteAdminBtn');btn.disabled=true;
  try{
    const d=await api('/api/mediation/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({partner:currentPartner})});
    if(!d.success)throw new Error(d.message||'เชิญแอดมินไม่สำเร็จ');
    await openMediationRoom(d.room.id);
    await loadMyMediationRooms();
  }catch(err){alert(err.message||'ขณะนี้ไม่มีแอดมินว่าง');}
  finally{btn.disabled=false;}
}
async function openMediationRoom(roomId){
  try{
    const d=await api('/api/mediation/'+encodeURIComponent(roomId));
    currentMediationId=roomId;currentMediationAdmin=!!d.is_admin;
    const room=d.room;
    currentPartner=(room.pair||[]).find(name=>name!==currentUsername)||null;
    document.getElementById('chatPartnerName').textContent='🛡️ ห้องคนกลางซื้อขาย';
    document.getElementById('chatPartnerAvatar').textContent='🛡️';
    document.getElementById('chatPartnerSubtitle').textContent='ผู้ซื้อ + ผู้ขาย + แอดมินคนกลาง';
    document.getElementById('chatOverlay').classList.add('show');
    setMediationControls('room',room);
    const input=document.getElementById('chatInput');input.placeholder='พิมพ์ข้อความถึงทุกคนในห้อง...';input.disabled=false;
    await loadMediationConversation();input.focus();
  }catch(err){alert(err.message||'เปิดห้องคนกลางไม่สำเร็จ');}
}
async function loadMediationConversation(){
  if(!currentMediationId)return;
  try{
    const d=await api('/api/mediation/'+encodeURIComponent(currentMediationId));
    const box=document.getElementById('chatMessages');const near=box.scrollHeight-box.scrollTop-box.clientHeight<110;
    const room=d.room;currentMediationAdmin=!!d.is_admin;setMediationControls('room',room);box.replaceChildren();
    const messages=room.messages||[];
    if(!messages.length){const empty=document.createElement('div');empty.className='empty-state';empty.textContent='เริ่มการพูดคุยได้เลย ทุกข้อความจะมองเห็นโดยผู้ซื้อ ผู้ขาย และแอดมินคนกลาง';box.append(empty);}
    messages.forEach(m=>{
      const wrap=document.createElement('div');wrap.className='msg-bubble '+(m.from===currentUsername?'msg-me':'msg-other');
      const sender=document.createElement('div');sender.style.cssText='font-size:.68rem;font-weight:800;margin-bottom:4px;opacity:.8';sender.textContent=m.from+(m.from===room.admin?' · แอดมินคนกลาง':'');wrap.append(sender);
      const content=document.createElement('div');content.textContent=m.text;wrap.append(content);
      const time=document.createElement('div');time.className='msg-time';time.textContent=formatNotificationTime(m.time);wrap.append(time);box.append(wrap);
    });
    if(near)box.scrollTop=box.scrollHeight;
  }catch(err){
    if(err.message&&/สิ้นสุด|ไม่พบห้อง/.test(err.message)){currentMediationId=null;currentMediationAdmin=false;document.getElementById('chatMessages').innerHTML='<div class="empty-state">การขายสิ้นสุดแล้ว ห้องคนกลางถูกปิด</div>';currentPartner=null;setMediationControls('closed');document.getElementById('chatInput').disabled=true;document.getElementById('chatInput').placeholder='ห้องนี้ปิดแล้ว';await loadMyMediationRooms();return;}
    console.error(err);
  }
}
async function loadMyMediationRooms(){
  try{
    const d=await api('/api/mediation/active');
    const body=document.getElementById('chatListBody');if(!body)return;
    const old=document.getElementById('mediationRoomList');if(old)old.remove();
    if(!d.rooms||!d.rooms.length)return;
    const wrap=document.createElement('div');wrap.id='mediationRoomList';wrap.style.cssText='padding:10px 12px;border-bottom:1px solid var(--border);background:rgba(212,175,55,.07)';
    const title=document.createElement('div');title.className='chat-list-caption';title.textContent='🛡️ ห้องคนกลางที่กำลังดำเนินการ';wrap.append(title);
    d.rooms.forEach(room=>{const b=document.createElement('button');b.type='button';b.className='mediation-invite-btn';b.style.cssText='display:block;width:100%;text-align:left;margin-top:6px';b.textContent='เปิดห้อง · '+(room.pair||[]).join(' ↔ ')+' · แอดมิน '+room.admin;b.onclick=()=>{document.getElementById('chatListPanel').classList.remove('show');openMediationRoom(room.id);};wrap.append(b);});
    body.prepend(wrap);
  }catch(e){console.error(e);}
}
async function endMediatedSale(){
  if(!currentMediationId||!currentMediationAdmin){alert('เฉพาะแอดมินคนกลางที่ได้รับมอบหมายเท่านั้น');return;}
  if(!confirm('ยืนยันจบการขายใช่หรือไม่? หลังยืนยัน ห้องคนกลางจะถูกปิดสำหรับผู้เข้าร่วมทุกคน'))return;
  try{
    const d=await api('/api/mediation/'+encodeURIComponent(currentMediationId)+'/end',{method:'POST'});
    if(!d.success)throw new Error(d.message||'จบการขายไม่สำเร็จ');
    currentMediationId=null;currentMediationAdmin=false;currentPartner=null;document.getElementById('chatMessages').replaceChildren();
    const msg=document.createElement('div');msg.className='empty-state';msg.textContent='จบการขายแล้ว ห้องคนกลางถูกปิด';document.getElementById('chatMessages').append(msg);
    document.getElementById('chatInput').disabled=true;document.getElementById('chatInput').placeholder='ห้องนี้ปิดแล้ว';setMediationControls('closed');await loadMyMediationRooms();await loadNotifications();
  }catch(err){alert(err.message||'จบการขายไม่สำเร็จ');}
}
function leaveMediationRoom(){currentMediationId=null;currentMediationAdmin=false;document.getElementById('chatInput').disabled=false;document.getElementById('chatInput').placeholder='พิมพ์ข้อความ...';setMediationControls('private');if(currentPartner)loadConversation();else{document.getElementById('chatPartnerName').textContent='แชท';document.getElementById('chatPartnerSubtitle').textContent='เลือกห้องคนกลางอีกครั้งเพื่อกลับเข้าสนทนา';document.getElementById('chatMessages').innerHTML='<div class="empty-state">ปิดหน้าต่างแชทหรือเปิดห้องคนกลางจากรายการแชท</div>';}}

async function openChatWith(name,avatar=null){
  currentMediationId=null;currentMediationAdmin=false;
  document.getElementById('chatInput').disabled=false;document.getElementById('chatInput').placeholder='พิมพ์ข้อความ...';setMediationControls('private');
  if(name===currentUsername){alert('ไม่สามารถแชตกับตัวเองได้');return;}
  currentPartner=name;document.getElementById('chatPartnerName').textContent=name;
  const avatarNode=document.getElementById('chatPartnerAvatar');avatarNode.replaceChildren();
  if(avatar){const img=document.createElement('img');img.src=avatar;img.alt='';img.onerror=()=>{avatarNode.textContent=(name||'?').slice(0,1).toUpperCase();};avatarNode.append(img);}else avatarNode.textContent=(name||'?').slice(0,1).toUpperCase();
  document.getElementById('chatPartnerSubtitle').textContent='FM_Market Messenger · บันทึกประวัติอัตโนมัติ';
  document.getElementById('chatOverlay').classList.add('show');await loadConversation();document.getElementById('chatInput').focus();
}
function closeChat(){document.getElementById('chatOverlay').classList.remove('show');currentPartner=null;currentMediationId=null;currentMediationAdmin=false;loadChatOverview();loadMyMediationRooms();}
const emojiChoices=['😀','😃','😄','😁','😆','😅','😂','🤣','🥹','😊','😍','🥰','😘','😎','🤔','😭','😢','😡','👍','👎','👏','🙏','🔥','❤️','💛','💖','🎉','✨','💯','🤝','🙌','😴','🤗','😇','😋','🤩','💔','💸','🚗','🎮','🐱','🐶','🌈','☀️','🌙','🍀','💎','👑'];
function initEmojiPicker(){const picker=document.getElementById('emojiPicker');if(!picker||picker.dataset.ready)return;emojiChoices.forEach(emoji=>{const b=document.createElement('button');b.type='button';b.className='emoji-choice';b.textContent=emoji;b.title=emoji;b.onclick=()=>{const input=document.getElementById('chatInput');input.value+=emoji;input.focus();};picker.append(b);});picker.dataset.ready='1';}
function toggleEmojiPicker(){initEmojiPicker();document.getElementById('emojiPicker').classList.toggle('show');document.getElementById('gifPanel').classList.remove('show');}
function toggleGifPanel(){document.getElementById('gifPanel').classList.toggle('show');document.getElementById('emojiPicker').classList.remove('show');}
function searchGif(){const q=encodeURIComponent(document.getElementById('chatInput').value.trim()||'reaction');window.open('https://tenor.com/search/'+q+'-gifs','_blank','noopener,noreferrer');}
async function loadConversation(){
  if(currentMediationId){await loadMediationConversation();return;}
  if(!currentPartner)return;
  try{
    const d=await api('/api/conversation/'+encodeURIComponent(currentPartner));
    const box=document.getElementById('chatMessages');const wasNearBottom=box.scrollHeight-box.scrollTop-box.clientHeight<110;const oldTop=box.scrollTop;
    box.replaceChildren();const messages=d.messages||[];
    if(!messages.length){const empty=document.createElement('div');empty.className='empty-state';empty.textContent='คุณและ '+currentPartner+' ยังไม่มีข้อความ เริ่มทักทายกันได้เลย 👋';box.append(empty);}
    const lastMineIndex=messages.reduce((idx,m,i)=>m.from===currentUsername?i:idx,-1);
    messages.forEach((m,i)=>{
      const wrap=document.createElement('div');wrap.className='msg-bubble '+(m.from===currentUsername?'msg-me':'msg-other');
      if(m.type==='gif'){const img=document.createElement('img');img.className='msg-gif';img.src=m.text;img.alt='GIF';img.loading='lazy';img.referrerPolicy='no-referrer';img.onerror=()=>{img.replaceWith(document.createTextNode('เปิด GIF ไม่ได้ — ลิงก์อาจหมดอายุ'));};wrap.append(img);}
      else{const content=document.createElement('div');content.textContent=m.text;wrap.append(content);}
      const time=document.createElement('div');time.className='msg-time';time.textContent=formatNotificationTime(m.time);time.title=parseNotificationTime(m.time)?'เวลาประเทศไทย: '+new Intl.DateTimeFormat('th-TH',{timeZone:'Asia/Bangkok',dateStyle:'medium',timeStyle:'short'}).format(parseNotificationTime(m.time)):m.time||'';wrap.append(time);
      if(i===lastMineIndex&&m.read){const receipt=document.createElement('div');receipt.className='msg-receipt';receipt.textContent='อ่านแล้ว ✓';wrap.append(receipt);}
      box.append(wrap);
    });
    if(wasNearBottom||!messages.length)box.scrollTop=box.scrollHeight;else box.scrollTop=oldTop;
    loadChatOverview();
  }catch(err){console.error(err);const box=document.getElementById('chatMessages');box.replaceChildren();const error=document.createElement('div');error.className='empty-state';error.textContent=err.message||'เปิดประวัติแชทไม่สำเร็จ';box.append(error);}
}
function onChatEnter(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChatMessage();}}
async function postChatPayload(payload){try{let d;if(currentMediationId){if(payload.type==='gif')throw new Error('ห้องคนกลางรองรับข้อความตัวอักษรในเวอร์ชันนี้');d=await api('/api/mediation/'+encodeURIComponent(currentMediationId)+'/message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:payload.text})});if(!d.success)throw new Error(d.message||'ส่งข้อความไม่สำเร็จ');await loadMediationConversation();return true;}if(!currentPartner){alert('กรุณาเลือกผู้ติดต่อก่อน');return false;}d=await api('/api/send-message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to:currentPartner,...payload})});if(!d.success)throw new Error(d.message||'ส่งข้อความไม่สำเร็จ');await loadConversation();loadNotifications();return true;}catch(err){alert(err.message);return false;}}
async function sendChatMessage(){const input=document.getElementById('chatInput');const message=input.value.trim();if(!message)return;if(await postChatPayload({text:message,type:'text'})){input.value='';document.getElementById('emojiPicker').classList.remove('show');}}
async function sendGifMessage(){const input=document.getElementById('gifUrlInput');const url=input.value.trim();if(!url){alert('วางลิงก์ GIF ก่อนส่ง');return;}if(await postChatPayload({text:url,type:'gif'})){input.value='';document.getElementById('gifPanel').classList.remove('show');}}
document.addEventListener('click',e=>{
  if(!e.target.closest('.notif-wrap'))document.getElementById('notifPanel').classList.remove('show');
  if(!e.target.closest('.chat-wrap'))document.getElementById('chatListPanel').classList.remove('show');
});
async function sendPresenceHeartbeat(){if(presenceBusy)return;presenceBusy=true;try{await api('/api/presence',{method:'POST'});}catch(e){}finally{presenceBusy=false;}}
loadNotifications();loadChatOverview();loadMyMediationRooms();sendPresenceHeartbeat();
setInterval(()=>{loadNotifications();loadChatOverview();loadMyMediationRooms();sendPresenceHeartbeat();if(currentPartner||currentMediationId)loadConversation();},20000);
</script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
