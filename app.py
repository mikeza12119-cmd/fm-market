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
async function loadProfile() {
  try {
    const d = await api('/api/profile'); if(!d.success) return;
    document.getElementById('profileUsername').textContent=d.username;
    document.getElementById('profileBio').value=d.bio || '';
    document.getElementById('profileCreated').textContent='สมัครเมื่อ '+(d.created_at || '-');
    const role = document.getElementById('profileRole'); role.textContent=d.role_info.name; role.className='profile-role '+d.role;
    const frame=document.getElementById('profileAvatar'); frame.className='profile-avatar-frame '+d.role;
    frame.replaceChildren();
    if(d.avatar){const img=document.createElement('img');img.src=d.avatar;img.className='profile-avatar-img';img.alt='รูปโปรไฟล์';frame.append(img);}
    else {const placeholder=document.createElement('div');placeholder.className='profile-avatar-placeholder';placeholder.textContent=(d.username[0]||'?').toUpperCase();frame.append(placeholder);}
  } catch(err){console.error(err);}
}
async function saveProfile() {
  try { const d=await api('/api/profile/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bio:document.getElementById('profileBio').value})}); alert(d.message || 'บันทึกแล้ว'); }
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
async function loadNotifications(){
  try {const d=await api('/api/notifications');const list=document.getElementById('notifList');list.replaceChildren();
    const badge=document.getElementById('notifBadge');badge.textContent=d.unread_count;badge.classList.toggle('show',d.unread_count>0);
    if(!d.notifications.length){list.innerHTML='<div class="empty-state">ไม่มีการแจ้งเตือน</div>';return;}
    [...d.notifications].reverse().forEach(n=>{const el=document.createElement('div');el.className='panel-item'+(!n.read?' unread':'');const name=document.createElement('div');name.className='panel-item-name';name.textContent=n.type==='message'?'💬 ข้อความใหม่':'แจ้งเตือน';const body=document.createElement('div');body.className='panel-item-text';body.textContent=n.text;const time=document.createElement('div');time.className='panel-item-time';time.textContent=n.time;el.append(name,body,time);list.append(el);});
  }catch(err){console.error(err);}
}
async function markAllNotifRead(){try{await api('/api/notifications/mark-read',{method:'POST'});loadNotifications();}catch(err){alert(err.message);}}
async function loadChatOverview(){
  try {const d=await api('/api/chat-overview');const body=document.getElementById('chatListBody');body.replaceChildren();const badge=document.getElementById('chatBadge');badge.textContent=d.total_unread;badge.classList.toggle('show',d.total_unread>0);const contacts=Object.entries(d.contacts).sort((a,b)=>b[1].time.localeCompare(a[1].time));
    if(!contacts.length){body.innerHTML='<div class="empty-state">ยังไม่มีข้อความ</div>';return;}
    contacts.forEach(([name,c])=>{const el=document.createElement('div');el.className='panel-item'+(c.unread?' unread':'');const title=document.createElement('div');title.className='panel-item-name';title.textContent=name+(c.unread?' ('+c.unread+')':'');const msg=document.createElement('div');msg.className='panel-item-text';msg.textContent=c.last_msg;const time=document.createElement('div');time.className='panel-item-time';time.textContent=c.time;el.append(title,msg,time);el.onclick=()=>{document.getElementById('chatListPanel').classList.remove('show');openChatWith(name);};body.append(el);});
  }catch(err){console.error(err);}
}
function markAllChatRead(){loadChatOverview();}
async function openChatWith(name){if(name===currentUsername){alert('ไม่สามารถแชตกับตัวเองได้');return;}currentPartner=name;document.getElementById('chatPartnerName').textContent=name;document.getElementById('chatOverlay').classList.add('show');await loadConversation();}
function closeChat(){document.getElementById('chatOverlay').classList.remove('show');currentPartner=null;loadChatOverview();}
async function loadConversation(){
  if(!currentPartner)return;
  try{const d=await api('/api/conversation/'+encodeURIComponent(currentPartner));const box=document.getElementById('chatMessages');box.replaceChildren();d.messages.forEach(m=>{const wrap=document.createElement('div');wrap.className='msg-bubble '+(m.from===currentUsername?'msg-me':'msg-other');const content=document.createElement('div');content.textContent=m.text;const time=document.createElement('div');time.className='msg-time';time.textContent=m.time;wrap.append(content,time);box.append(wrap);});box.scrollTop=box.scrollHeight;loadChatOverview();}
  catch(err){alert(err.message);}
}
function onChatEnter(e){if(e.key==='Enter')sendChatMessage();}
async function sendChatMessage(){
  const input=document.getElementById('chatInput');const message=input.value.trim();if(!message||!currentPartner)return;
  try{const d=await api('/api/send-message',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to:currentPartner,text:message})});if(!d.success)throw new Error(d.message||'ส่งข้อความไม่สำเร็จ');input.value='';await loadConversation();loadNotifications();}
  catch(err){alert(err.message);}
}
document.addEventListener('click',e=>{
  if(!e.target.closest('.notif-wrap'))document.getElementById('notifPanel').classList.remove('show');
  if(!e.target.closest('.chat-wrap'))document.getElementById('chatListPanel').classList.remove('show');
});
loadNotifications();loadChatOverview();
setInterval(()=>{loadNotifications();loadChatOverview();if(currentPartner)loadConversation();},10000);
</script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
