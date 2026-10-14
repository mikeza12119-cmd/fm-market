from flask import Flask, render_template_string, request, jsonify, session, send_from_directory
import uuid
import json
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-development-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
DB_FILE = os.environ.get("DB_FILE", os.path.join(DATA_DIR, "database.json"))
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(DATA_DIR, "uploads"))
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
POST_LIFETIME_HOURS = 3

os.makedirs(AVATAR_FOLDER, exist_ok=True)

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def json_body():
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
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)
        return default_data
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = default_data.copy()
    for k in default_data:
        if k not in data:
            data[k] = default_data[k]
    for uname in data["users"]:
        user = data["users"][uname]
        if "role" not in user: user["role"] = "member"
        if "avatar" not in user: user["avatar"] = None
        if "bio" not in user: user["bio"] = ""
        if "profile_theme" not in user: user["profile_theme"] = "#d4af37"
        if "profile_banner" not in user: user["profile_banner"] = None
    now = datetime.now()
    fresh_posts = []
    for p in data["posts"]:
        try:
            post_time = datetime.strptime(p["time"], '%d/%m/%Y %H:%M')
            if now - post_time <= timedelta(hours=POST_LIFETIME_HOURS):
                fresh_posts.append(p)
        except Exception:
            fresh_posts.append(p)
    data["posts"] = fresh_posts
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data

def save_database(data):
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
    return render_template_string(
        MAIN_PAGE,
        posts=db["posts"],
        news=db["news"],
        categories=db["categories"],
        session_user=session.get('user'),
        get_role_config=get_role_config,
        all_users=db["users"]
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
        return jsonify({"success": False})
    db = load_database()
    uname = session['user']['username']
    u = db["users"].get(uname)
    return jsonify({
        "success": True,
        "username": uname,
        "role": u["role"],
        "role_info": get_role_config(u["role"]),
        "avatar": u.get("avatar"),
        "bio": u.get("bio", ""),
        "profile_theme": u.get("profile_theme", "#d4af37"),
        "profile_banner": u.get("profile_banner"),
        "created_at": u.get("created_at", "-")
    })

@app.route('/api/profile/<username>', methods=['GET'])
def get_public_profile(username):
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

@app.route('/api/admin/set-role', methods=['POST'])
def set_role():
    if 'user' not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"}), 401
    db = load_database()
    actor = db["users"].get(session["user"].get("username"), {})
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
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบ"})
    db = load_database()
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
        "author": session['user']['username'],
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
            conversations.setdefault(other, {"last_msg": "", "type": "text", "time": "", "unread": 0, "_message": msg})["unread"] += 1
    for item in conversations.values():
        item.pop("_message", None)
    total_unread = sum(item["unread"] for item in conversations.values())
    return jsonify({"success": True, "contacts": conversations, "total_unread": total_unread})

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
    save_database(db)
    return jsonify({"success": True, "message": new_msg})

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

MAIN_PAGE = '''
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
.panel-item-time{font-size:.7rem;color:#555;margin-top:4px}
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
.chat-wrap .dropdown-panel{position:fixed;top:auto;right:22px;bottom:88px;width:min(340px,calc(100vw - 28px));max-height:min(480px,calc(100vh - 130px))}
@media(max-width:520px){.chat-overlay{padding:12px 8px 86px}.chat-window{height:min(70vh,560px);width:calc(100vw - 16px)}.chat-launcher{right:15px;bottom:15px}}
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
.form-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:24px;max
