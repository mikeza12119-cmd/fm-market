from flask import Flask, render_template_string, request, jsonify, session, send_from_directory
import uuid
import json
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "fm_market_secure_key_2026_fixed_v1"

DB_FILE = "database.json"
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
POST_LIFETIME_HOURS = 3

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def load_database():
    default_data = {
        "users": {
            "admin": {
                "password": generate_password_hash("admin123", method='pbkdf2:sha256'),
                "role": "admin",
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
        session_user=session.get('user')
    )

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
      <input type="password" id="rp" placeholder="ตั้งรหัสผ่าน (4 ตัวขึ้นไป ยาวได้เท่าไหร่ก็ได้)" required autocomplete="new-password">
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
.brand{font-size:1.4rem;font-weight:900}
.brand span{color:var(--gold)}
.nav{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.btn{padding:9px 16px;border:none;border-radius:var(--r);font-weight:700;transition:.2s}
.btn:hover{transform:translateY(-2px)}
.btn-gold{background:linear-gradient(90deg,var(--gold),var(--gold2));color:#000}
.btn-blue{background:var(--blue);color:#fff}
.btn-ghost{background:transparent;border:1px solid var(--border);color:var(--text)}
.btn-sm{padding:6px 12px;font-size:.85rem}
.btn-red{background:var(--red);color:#fff;border-color:var(--red)}
.badge{font-size:.7rem;padding:3px 8px;border-radius:12px;font-weight:700}
.badge-admin{background:var(--red);color:#fff}
.badge-member{background:var(--blue);color:#fff}
.notif-wrap, .chat-wrap{position:relative}
.bell-btn, .chat-btn-nav{background:transparent;border:none;color:var(--text);font-size:1.2rem;padding:6px 10px;cursor:pointer;position:relative}
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
.post-title{font-size:1.1rem;margin-bottom:8px}
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
</style>
</head>
<body>
<header>
  <div class="head">
    <div class="brand">FM<span>_Market</span></div>
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
      <span>{{ session_user.username }}</span>
      {% if session_user.role == 'admin' %}
      <span class="badge badge-admin">ผู้ดูแล</span>
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
      <div class="postcard" data-cat="{{p.category}}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <h3 class="post-title">{{ p.title }}</h3>
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
            <option value="{{k}}">{{v.icon}} {{v.name}}</option>
            {% endfor %}
          </select>
        </div>
        <div class="form-group">
          <label>หัวข้อ</label>
          <input type="text" id="title" class="form-input" placeholder="เช่น ขายเงิน M 1,000,000 ราคา..." required>
        </div>
        <div class="form-group">
          <label>รายละเอียด</label>
          <textarea id="detail" class="form-input" rows="5" placeholder="ระบุจำนวน ราคา เงื่อนไข..."></textarea>
        </div>
        <div class="form-group">
          <label>รูปภาพ (สูงสุด 5 รูป)</label>
          <div class="upload-area" onclick="document.getElementById('imageInput').click()">
            📷 คลิกเพื่อเลือกไฟล์
            <input type="file" id="imageInput" accept="image/*" multiple style="display:none">
          </div>
          <div id="previewRow" class="preview-row"></div>
        </div>
        <button type="submit" class="btn btn-gold" style="width:100%">📤 ลงประกาศ</button>
      </form>
    </div>
  </div>
</main>

<script>
let selectedImgs = [];
let currentChatPartner = null;
let pollTimer = null;

async function refreshBadges(){
  try{
    const [chatRes, notifRes] = await Promise.all([
      fetch('/api/chat-overview'),
      fetch('/api/notifications')
    ]);
    const chatData = await chatRes.json();
    const notifData = await notifRes.json();
    
    const chatBadge = document.getElementById('chatBadge');
    const notifBadge = document.getElementById('notifBadge');
    
    if(chatData.total_unread > 0){
      chatBadge.textContent = chatData.total_unread;
      chatBadge.classList.add('show');
    } else {
      chatBadge.classList.remove('show');
    }
    
    if(notifData.unread_count > 0){
      notifBadge.textContent = notifData.unread_count;
      notifBadge.classList.add('show');
    } else {
      notifBadge.classList.remove('show');
    }
  }catch(e){console.error(e)}
}

async function toggleNotif(){
  const panel = document.getElementById('notifPanel');
  panel.classList.toggle('show');
  if(panel.classList.contains('show')) await loadNotifList();
  else document.getElementById('chatListPanel').classList.remove('show');
}

async function loadNotifList(){
  const res = await fetch('/api/notifications');
  const d = await res.json();
  const list = document.getElementById('notifList');
  if(!d.notifications.length){
    list.innerHTML = '<div class="empty-state">ยังไม่มีการแจ้งเตือน</div>';
    return;
  }
  list.innerHTML = d.notifications.map(n=>`
    <div class="panel-item ${!n.read?'unread':''}">
      <div class="panel-item-name">${n.from || 'ระบบ'}</div>
      <div class="panel-item-text">${n.text}</div>
      <div class="panel-item-time">${n.time}</div>
    </div>
  `).join('');
}

async function markAllNotifRead(){
  await fetch('/api/notifications/mark-read',{method:'POST'});
  await loadNotifList();
  await refreshBadges();
}

async function clearAllNotif(){
  if(!confirm('ล้างรายการแจ้งเตือนทั้งหมด?')) return;
  document.getElementById('notifList').innerHTML = '<div class="empty-state">ล้างแล้ว</div>';
  await refreshBadges();
}

async function toggleChatList(){
  const panel = document.getElementById('chatListPanel');
  panel.classList.toggle('show');
  if(panel.classList.contains('show')) await loadChatList();
  else document.getElementById('notifPanel').classList.remove('show');
}

async function loadChatList(){
  const res = await fetch('/api/chat-overview');
  const d = await res.json();
  const list = document.getElementById('chatListBody');
  if(!Object.keys(d.contacts).length){
    list.innerHTML = '<div class="empty-state">ยังไม่มีข้อความ — ไปทักคนอื่นก่อนเลย!</div>';
    return;
  }
  list.innerHTML = Object.entries(d.contacts).map(([name, info])=>`
    <div class="panel-item ${info.unread>0?'unread':''}" onclick="openChatWith('${name}')">
      <div class="panel-item-name">${name} ${info.unread>0?`<span style="color:var(--red);font-size:.7rem">(${info.unread})</span>`:''}</div>
      <div class="panel-item-text">${info.last_msg}</div>
      <div class="panel-item-time">${info.time}</div>
    </div>
  `).join('');
}

async function markAllChatRead(){
  await fetch('/api/notifications/mark-read',{method:'POST'});
  await loadChatList();
  await refreshBadges();
}

async function openChatWith(name){
  currentChatPartner = name;
  document.getElementById('chatPartnerName').textContent = `คุยกับ ${name}`;
  document.getElementById('chatOverlay').classList.add('show');
  document.getElementById('chatListPanel').classList.remove('show');
  document.getElementById('notifPanel').classList.remove('show');
  await loadChatMessages();
}

function closeChat(){
  document.getElementById('chatOverlay').classList.remove('show');
  currentChatPartner = null;
}

async function loadChatMessages(){
  if(!currentChatPartner) return;
  const res = await fetch(`/api/conversation/${currentChatPartner}`);
  const d = await res.json();
  const box = document.getElementById('chatMessages');
  if(!d.messages.length){
    box.innerHTML = '<div class="empty-state">ยังไม่มีข้อความ พิมพ์ข้อความแรกได้เลย!</div>';
    return;
  }
  box.innerHTML = d.messages.map(m=>`
    <div class="msg-bubble ${m.from === '{{ session_user.username }}'?'msg-me':'msg-other'}">
      <div>${m.text}</div>
      <div class="msg-time">${m.time}</div>
    </div>
  `).join('');
  box.scrollTop = box.scrollHeight;
  await refreshBadges();
}

async function sendChatMessage(){
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if(!text || !currentChatPartner) return;
  input.value = '';
  await fetch('/api/send-message',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({to:currentChatPartner, text:text})
  });
  await loadChatMessages();
  await loadChatList();
}

function onChatEnter(e){
  if(e.key === 'Enter') sendChatMessage();
}

document.getElementById('imageInput').addEventListener('change', async e=>{
  for(const file of e.target.files){
    const fd = new FormData();
    fd.append('image', file);
    const res = await fetch('/api/upload-image', {method:'POST', body:fd});
    const d = await res.json();
    if(d.success){
      selectedImgs.push(d.url);
      renderPreview();
    }else alert('อัปโหลดไม่ได้: '+d.message);
  }
  e.target.value='';
});
function renderPreview(){
  const c=document.getElementById('previewRow');
  c.innerHTML=selectedImgs.map((u,i)=>`<div class="preview-item"><img src="${u}"><button class="preview-del" onclick="selectedImgs.splice(${i},1);renderPreview()">×</button></div>`).join('');
}
document.getElementById('postForm').addEventListener('submit',async e=>{
  e.preventDefault();
  const res=await fetch('/api/post',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      category:document.getElementById('category').value,
      title:document.getElementById('title').value,
      detail:document.getElementById('detail').value,
      images:selectedImgs
    })
  });
  const d=await res.json();
  if(d.success){
    alert('✅ ลงประกาศสำเร็จ');
    selectedImgs=[];
    renderPreview();
    showTab('market');
    location.reload();
  }else alert(d.message);
});
function showTab(name){
  document.querySelectorAll('.content-tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab'+name.charAt(0).toUpperCase()+name.slice(1)).classList.add('active');
}
function filterCat(cat){
  document.querySelectorAll('.cattab').forEach(t=>t.classList.toggle('active',t.dataset.cat===cat));
  document.querySelectorAll('.postcard').forEach(p=>{
    p.style.display=(cat==='all' || p.dataset.cat===cat)?'block':'none';
  });
}
async function delPost(id){
  if(!confirm('ลบจริงหรือไม่?'))return;
  const res=await fetch('/api/post/'+id,{method:'DELETE'});
  const d=await res.json();
  if(d.success)location.reload();
  else alert(d.message);
}
async function doLogout(){
  if(!confirm('ออกจากระบบหรือไม่?'))return;
  await fetch('/api/logout');
  location.href='/';
}

refreshBadges();
pollTimer = setInterval(refreshBadges, 30000);
</script>
</body>
</html>
'''

if __name__ == '__main__':
    print("="*60)
    print("🖤 FM_Market — ระบบแจ้งเตือนครบถ้วน")
    print("✅ แจ้งเตือนคนทักมา + จำนวนข้อความไม่อ่าน")
    print("✅ แชทส่วนตัวทำงาน")
    print("="*60)
