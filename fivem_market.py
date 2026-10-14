from flask import Flask, render_template_string, request, jsonify, session, send_from_directory
import uuid
import json
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "fm_market_secure_key_2026_fixed_v2"

DB_FILE = "database.json"
UPLOAD_FOLDER = "uploads"
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
POST_LIFETIME_HOURS = 3

os.makedirs(AVATAR_FOLDER, exist_ok=True)

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def get_role_config(role):
    roles = {
        "admin": {
            "name": "ผู้ดูแลระบบ",
            "badge": "👑",
            "border": "linear-gradient(135deg, #ffd700, #ffed4e, #ffd700)",
            "bg_badge": "linear-gradient(90deg, #b8860b, #ffd700)",
            "text_color": "#ffd700"
        },
        "vip": {
            "name": "สมาชิก VIP",
            "badge": "⭐",
            "border": "linear-gradient(135deg, #9932cc, #da70d6, #9932cc)",
            "bg_badge": "linear-gradient(90deg, #8b00ff, #da70d6)",
            "text_color": "#da70d6"
        },
        "member": {
            "name": "สมาชิกทั่วไป",
            "badge": "👤",
            "border": "linear-gradient(135deg, #4b5563, #6b7280, #4b5563)",
            "bg_badge": "linear-gradient(90deg, #374151, #6b7280)",
            "text_color": "#9ca3af"
        }
    }
    return roles.get(role, roles["member"])

def load_database():
    default_data = {
        "users": {
            "admin": {
                "password": generate_password_hash("admin123", method='pbkdf2:sha256'),
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
        if "role" not in user:
            user["role"] = "member"
        if "avatar" not in user:
            user["avatar"] = None
        if "bio" not in user:
            user["bio"] = ""
    now = datetime.now()
    fresh_posts = []
    for p in data["posts"]:
        try:
            post_time = datetime.strptime(p["time"], '%d/%m/%Y %H:%M')
            if now - post_time <= timedelta(hours=POST_LIFETIME_HOURS):
                fresh_posts.append(p)
        except:
            fresh_posts.append(p)
    data["posts"] = fresh_posts
    save_database(data)
    return data

def save_database(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
        old_path = db["users"][uname]["avatar"].lstrip("/")
        if os.path.exists(old_path):
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
        "created_at": u.get("created_at", "-")
    })

@app.route('/api/profile/update', methods=['POST'])
def update_profile():
    if 'user' not in session:
        return jsonify({"success": False})
    db = load_database()
    uname = session['user']['username']
    d = request.json
    if "bio" in d:
        db["users"][uname]["bio"] = d["bio"].strip()
    save_database(db)
    return jsonify({"success": True, "message": "บันทึกข้อมูลเรียบร้อย"})

@app.route('/api/admin/set-role', methods=['POST'])
def set_role():
    if 'user' not in session or session['user']['role'] != 'admin':
        return jsonify({"success": False, "message": "ไม่มีสิทธิ์"})
    d = request.json
    target_user = d.get("username", "").strip()
    new_role = d.get("role")
    if new_role not in ["admin", "vip", "member"]:
        return jsonify({"success": False, "message": "ยศไม่ถูกต้อง"})
    db = load_database()
    if target_user not in db["users"]:
        return jsonify({"success": False, "message": "ไม่พบผู้ใช้"})
    db["users"][target_user]["role"] = new_role
    save_database(db)
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
    d = request.json
    u = d['username'].strip()
    p = d['password']
    if len(u) < 2:
        return jsonify({"success": False, "message": "ชื่อต้อง 2 ตัวอักษรขึ้นไป"})
    if u in db['users']:
        return jsonify({"success": False, "message": "ชื่อนี้มีคนใช้แล้ว"})
    if len(p) < 4:
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
    session['user'] = {"username": u, "role": "member"}
    return jsonify({"success": True, "user": {"username": u, "role": "member"}})

@app.route('/api/login', methods=['POST'])
def login():
    db = load_database()
    d = request.json
    u = d['username'].strip()
    p = d['password']
    user = db['users'].get(u)
    if not user:
        return jsonify({"success": False, "message": "ชื่อหรือรหัสผ่านไม่ถูกต้อง"})
    if not check_password_hash(user['password'], p):
        return jsonify({"success": False, "message": "ชื่อหรือรหัสผ่านไม่ถูกต้อง"})
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
    d = request.json
    if d.get('category') not in db["categories"]:
        return jsonify({"success": False, "message": "หมวดหมู่ไม่ถูกต้อง"})
    if not d.get("title", "").strip():
        return jsonify({"success": False, "message": "กรุณากรอกหัวข้อ"})
    post = {
        "id": str(uuid.uuid4())[:8],
        "category": d["category"],
        "title": d["title"].strip(),
        "detail": d.get("detail", "").strip(),
        "images": d.get("images", [])[:5],
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
    keep = []
    found = False
    for p in db["posts"]:
        if p["id"] == post_id and (p["author"] == uname or session['user']['role'] == 'admin'):
            found = True
        else:
            keep.append(p)
    if not found:
        return jsonify({"success": False, "message": "ไม่พบหรือไม่มีสิทธิ์ลบ"})
    db["posts"] = keep
    save_database(db)
    return jsonify({"success": True})

@app.route('/api/chat-overview', methods=['GET'])
def chat_overview():
    if 'user' not in session:
        return jsonify({"success": False})
    me = session['user']['username']
    db = load_database()
    partners = {}
    for msg in db["messages"]:
        if msg["from"] != me and msg["to"] != me:
            continue
        other = msg["to"] if msg["from"] == me else msg["from"]
        if other not in partners:
            partners[other] = {
                "last_msg": msg["text"],
                "time": msg["time"],
                "unread": 0
            }
        if msg["time"] > partners[other]["time"]:
            partners[other]["last_msg"] = msg["text"]
            partners[other]["time"] = msg["time"]
        if msg["to"] == me and not msg.get("read"):
            partners[other]["unread"] += 1
    total_unread = sum(p["unread"] for p in partners.values())
    return jsonify({
        "success": True,
        "contacts": partners,
        "total_unread": total_unread
    })

@app.route('/api/conversation/<partner>', methods=['GET'])
def get_conversation(partner):
    if 'user' not in session:
        return jsonify({"success": False})
    me = session['user']['username']
    db = load_database()
    for msg in db["messages"]:
        if msg["from"] == partner and msg["to"] == me:
            msg["read"] = True
    save_database(db)
    conv = [m for m in db["messages"]
            if (m["from"] == me and m["to"] == partner) or
               (m["from"] == partner and m["to"] == me)]
    return jsonify({"success": True, "messages": conv})

@app.route('/api/send-message', methods=['POST'])
def send_message():
    if 'user' not in session:
        return jsonify({"success": False})
    d = request.json
    db = load_database()
    me = session['user']['username']
    receiver = d.get("to")
    text = d.get("text", "").strip()
    if not receiver or not text or receiver == me or receiver not in db["users"]:
        return jsonify({"success": False, "message": "ข้อมูลไม่ถูกต้อง"})
    new_msg = {
        "id": str(uuid.uuid4())[:8],
        "from": me,
        "to": receiver,
        "text": text,
        "time": datetime.now().strftime('%d/%m/%Y %H:%M'),
        "read": False
    }
    db["messages"].append(new_msg)
    db["notifications"].append({
        "id": str(uuid.uuid4())[:8],
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
:root{--bg:#050508;--card:#12121a;--gold:#d4af37;--gold2:#f0c808;
--text:#fff;--text2:#a0a0b5;--border:#282838;--error:#e53935}
body{background:linear-gradient(180deg,#000,#050508);color:var(--text);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.wrap{max-width:420px;width:100%}
.logo{text-align:center;margin-bottom:40px;cursor:pointer}
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
  <div class="logo" onclick="location.href='/'"><h1>FM<span>_Market</span></h1></div>
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
    body:JSON.stringify({
      username:document.getElementById('lu').value,
      password:document.getElementById('lp').value
    })
  });
  const d=await r.json();
  if(d.success){
    alert('✅ เข้าสู่ระบบสำเร็จ');
    window.location.href='/';
  } else {
    const errBox = document.getElementById('loginErr');
    errBox.textContent = '❌ ' + d.message;
    errBox.style.display='block';
  }
}
async function doR(e){
  e.preventDefault();
  document.getElementById('regErr').style.display='none';
  const r=await fetch('/api/register',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      username:document.getElementById('ru').value,
      password:document.getElementById('rp').value
    })
  });
  const d=await r.json();
  if(d.success){
    alert('✅ สมัครสำเร็จ! กำลังเข้าสู่ระบบ...');
    window.location.href='/';
  } else {
    const errBox = document.getElementById('regErr');
    errBox.textContent = '❌ ' + d.message;
    errBox.style.display='block';
  }
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
:root{--bg:#050508;--card:#12121a;--gold:#d4af37;--gold2:#f0c808;--blue:#2563eb;--red:#c41e3a;--green:#10b981;--text:#fff;--soft:#9090a5;--border:#282838;--r:14px}
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui,sans-serif}
body{background:var(--bg);color:var(--text);line-height:1.6;padding-bottom:80px}
header{position:sticky;top:0;z-index:999;background:rgba(5,5,8,.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:14px 20px}
.head{max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}
.brand{font-size:1.4rem;font-weight:900;cursor:pointer;transition:.2s}
.brand:hover{transform:scale(1.05)}
.brand span{color:var(--gold)}
.nav{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.btn{padding:9px 16px;border:none;border-radius:var(--r);font-weight:700;transition:.2s;cursor:pointer}
.btn:hover{transform:translateY(-2px)}
.btn-gold{background:linear-gradient(90deg,var(--gold),var(--gold2));color:#000}
.btn-blue{background:var(--blue);color:#fff}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--text)}
.btn-sm{padding:6px 12px;font-size:.85rem}
.btn-red{background:var(--red);color:#fff;border-color:var(--red)}
.badge{font-size:.7rem;padding:3px 8px;border-radius:12px;font-weight:700}
.badge-admin{background:var(--red);color:#fff}
.badge-member{background:var(--blue);color:#fff}
.notif-wrap, .chat-wrap, .profile-wrap{position:relative}
.bell-btn, .chat-btn-nav, .profile-btn{background:transparent;border:none;color:var(--text);font-size:1.2rem;padding:6px 10px;cursor:pointer;position:relative}
.badge-count{position:absolute;top:-2px;right:-4px;background:var(--red);color:#fff;font-size:.65rem;min-width:18px;height:18px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;transform:scale(0);transition:.2s}
.badge-count.show{transform:scale(1)}
.dropdown-panel{position:absolute;top:100%;right:0;margin-top:8px;width:340px;background:var(--card);border:1px solid var(--border);border-radius:var(--r);box-shadow:0 10px 40px rgba(0,0,0,.5);display:none;flex-direction:column;max-height:480px;overflow:hidden;z-index:2000}
.dropdown-panel.show{display:flex}
.panel-head{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
.panel-title{font-weight:700}
.panel-actions button{background:none;border:none;color:var(--soft);font-size:.8rem;margin-left:8px;cursor:pointer}
.panel-list{overflow-y:auto;flex:1}
.panel-item{padding:12px 16px;border-bottom:1px solid var(--border);cursor:pointer;transition:.2s}
.panel-item:hover{background:rgba(37,99,235,.1)}
.panel-item.unread{background:rgba(212,175,55,.12);border-left:3px solid var(--gold)}
.panel-item-name{font-weight:600;font-size:.9rem}
.panel-item-text{font-size:.85rem;color:var(--soft);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.panel-item-time{font-size:.7rem;color:#555;margin-top:4px}
.empty-state{padding:30px;text-align:center;color:var(--soft);font-size:.9rem}
.chat-overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:3000;display:none;align-items:flex-end;justify-content:flex-end;padding:20px}
.chat-overlay.show{display:flex}
.chat-window{width:100%;max-width:400px;background:var(--card);border:1px solid var(--border);border-radius:var(--r);display:flex;flex-direction:column;max-height:520px;box-shadow:0 10px 40px rgba(0,0,0,.5)}
.chat-header{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
.chat-close{background:none;border:none;color:var(--soft);font-size:1.3rem;cursor:pointer}
.chat-messages{flex:1;padding:16px;overflow-y:auto;min-height:300px;background:#0a0a10;display:flex;flex-direction:column;gap:10px}
.msg-bubble{max-width:80%;padding:10px 14px;border-radius:18px;line-height:1.4}
.msg-me{background:#1e3a5f;align-self:flex-end;border-bottom-right-radius:4px}
.msg-other{background:#2a2a3a;align-self:flex-start;border-bottom-left-radius:4px}
.msg-time{font-size:.7rem;color:var(--soft);margin-top:4px;text-align:right}
.chat-input-area{display:flex;gap:8px;padding:12px;border-top:1px solid var(--border)}
.chat-input-area input{flex:1;background:#0a0a10;border:1px solid var(--border);border-radius:var(--r);padding:10px 14px;color:var(--text);font-size:.9rem}
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
.post-title{font-size:1.1rem;margin-bottom:4px}
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
.preview-del{position:absolute;top:4px;right:4px;background:rgba(0,0,0,.7);color:#fff;border:none;width:24px;height:24px;border-radius:50%;font-size:1rem;display:flex;align-items:center;justify-content:center}
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
        <button class="bell-btn" onclick="toggleNotif()">
          🔔
          <span id="notifBadge" class="badge-count">0</span>
        </button>
        <div id="notifPanel" class="dropdown-panel">
          <div class="panel-head">
            <span class="panel-title">🔔 การแจ้งเตือน</span>
            <div class="panel-actions">
              <button onclick="markAllNotifRead()">อ่านทั้งหมด</button>
              <button onclick="clearAllNotif()">ล้าง</button>
            </div>
          </div>
          <div id="notifList" class="panel-list">
            <div class="empty-state">กำลังโหลด...</div>
          </div>
        </div>
      </div>
      <div class="chat-wrap">
        <button class="bell-btn" onclick="toggleChatList()">
          💬
          <span id="chatBadge" class="badge-count">0</span>
        </button>
        <div id="chatListPanel" class="dropdown-panel">
          <div class="panel-head">
            <span class="panel-title">💬 ข้อความที่คุยด้วย</span>
            <div class="panel-actions">
              <button onclick="markAllChatRead()">อ่านทั้งหมด</button>
            </div>
          </div>
          <div id="chatListBody" class="panel-list">
            <div class="empty-state">กำลังโหลด...</div>
          </div>
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

<div id="chatOverlay" class="chat-overlay" onclick="if(event.target===this)closeChat()">
  <div class="chat-window" onclick="event.stopPropagation()">
    <div class="chat-header">
      <span id="chatPartnerName" class="panel-title">แชท</span>
      <button class="chat-close" onclick="closeChat()">×</button>
    </div>
    <div id="chatMessages" class="chat-messages">
      <div class="empty-state">กำลังโหลด...</div>
    </div>
    <div class="chat-input-area">
      <input type="text" id="chatInput" placeholder="พิมพ์ข้อความ..." onkeydown="onChatEnter(event)">
      <button class="btn btn-gold" onclick="sendChatMessage()">ส่ง</button>
    </div>
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
      {% set author_data = all_users[p.author] %}
      {% set role_info = get_role_config(author_data.role) %}
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
              <span>{{role_info.badge}} {{p.author}}</span>
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
          <span>👤 {{ p.author }}</span>
          <span>{{ p.time }}</span>
          <button class="chat-btn-post" onclick="openChatWith('{{p.author}}')">💬 คุยด้วย</button>
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
      <form id="postForm">
        <div class="form-group">
          <label>หมวดหมู่</label>
          <select id="category" class="form-input">
            {% for k,v in categories.items() %}
