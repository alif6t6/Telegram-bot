# ╔══════════════════════════════════════════════════════════════════╗
# ║         🌺 ULTRA VPS HOSTING BOT — PREMIUM EDITION 🌺          ║
# ║              Multi-Process | ZIP Support | 4-5K Users           ║
# ╚══════════════════════════════════════════════════════════════════╝

import os, sys, asyncio, subprocess, psutil, time, json, zipfile
import shutil, threading, random, string, re, hashlib, tarfile, signal
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler

load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
import logging, sqlite3

try:
    import nest_asyncio
    nest_asyncio.apply()
except: pass

try:
    import GPUtil; GPU_AVAILABLE = True
except: GPU_AVAILABLE = False

try:
    import nbformat
    from nbconvert.preprocessors import ExecutePreprocessor
    NOTEBOOK_SUPPORT = True
except: NOTEBOOK_SUPPORT = False

# ══════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════
BOT_TOKEN        = os.environ.get("BOT_TOKEN", "")
OWNER_ID         = int(os.environ.get("OWNER_ID", "0"))
SUPPORT_USER     = os.environ.get("SUPPORT_USERNAME", "support")
MAX_SIZE_FREE    = 50  * 1024 * 1024   # 50MB
MAX_SIZE_PREMIUM = 500 * 1024 * 1024   # 500MB
MAX_PROC_FREE    = 3                    # free user max processes
MAX_PROC_PREMIUM = 20                   # premium max processes

if not BOT_TOKEN or not OWNER_ID:
    print("❌ Set BOT_TOKEN and OWNER_ID in .env!"); sys.exit(1)

# ══════════════════════════════════════════════
# PATHS
# ══════════════════════════════════════════════
BASE   = Path(os.getcwd()) / "vps_data"
DB     = str(BASE / "vps.db")
FILES  = BASE / "files"
LOGS   = BASE / "logs"
for d in [BASE, FILES, LOGS]: d.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════
# BOLD FONT
# ══════════════════════════════════════════════
def tb(t):
    n='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    b='𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗'
    return t.translate(str.maketrans(n,b)) if t else t
def mn(t): return f"`{t}`"

# ══════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════
_lock = threading.Lock()

def db_run(q, p=(), fetch=None):
    with _lock:
        c = sqlite3.connect(DB, check_same_thread=False, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA cache_size=10000")
        try:
            cur = c.execute(q, p)
            c.commit()
            if fetch == 'one': return cur.fetchone()
            if fetch == 'all': return cur.fetchall()
            return cur.lastrowid
        except Exception as e:
            logger.error(f"DB: {e}")
            return None
        finally:
            c.close()

def init_db():
    tables = [
        '''CREATE TABLE IF NOT EXISTS users(
            uid INTEGER PRIMARY KEY, uname TEXT, fname TEXT,
            banned INTEGER DEFAULT 0, first_seen TEXT, last_seen TEXT,
            credits INTEGER DEFAULT 3, verified INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT 0, ref_code TEXT UNIQUE,
            total_refs INTEGER DEFAULT 0, is_premium INTEGER DEFAULT 0,
            premium_expiry TEXT, auto_restart INTEGER DEFAULT 0,
            total_runs INTEGER DEFAULT 0, last_active TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS files(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER, fname TEXT, fpath TEXT, ftype TEXT,
            uploaded TEXT, main_file TEXT, fsize INTEGER DEFAULT 0,
            run_count INTEGER DEFAULT 0, is_zip INTEGER DEFAULT 0,
            extract_path TEXT
        )''',
        '''CREATE TABLE IF NOT EXISTS processes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER, file_id INTEGER, pkey TEXT,
            started TEXT, status TEXT DEFAULT 'running'
        )''',
        '''CREATE TABLE IF NOT EXISTS packages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER, pkg TEXT, installed TEXT,
            UNIQUE(uid, pkg)
        )''',
        '''CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, val TEXT)''',
        '''CREATE TABLE IF NOT EXISTS verify(
            uid INTEGER PRIMARY KEY, correct TEXT,
            options TEXT, expires TEXT, tries INTEGER DEFAULT 0
        )''',
    ]
    for t in tables: db_run(t)
    for k,v in [('start_time', str(time.time())), ('maintenance','0'), ('free_credits','3'), ('version','2.0')]:
        db_run("INSERT OR IGNORE INTO settings(key,val) VALUES(?,?)", (k,v))
    logger.info(f"✅ DB ready: {DB}")

init_db()

# ══════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════
def fmt_bytes(b):
    for u in ['B','KB','MB','GB','TB']:
        if b < 1024: return f"{b:.1f}{u}"
        b /= 1024
    return f"{b:.1f}PB"

def fmt_time(s):
    h,m,s2 = int(s//3600), int((s%3600)//60), int(s%60)
    return f"{h}h{m}m{s2}s" if h else f"{m}m{s2}s"

def pbar(v, mx, l=12):
    f = int((v/mx)*l) if mx else 0
    return f"{'█'*f}{'░'*(l-f)}"

def file_icon(name):
    e = Path(name).suffix.lower()
    return {'.py':'🐍','.js':'🟨','.ts':'🔷','.sh':'📜','.zip':'📦',
            '.tar':'📦','.gz':'📦','.html':'🌐','.css':'🎨','.json':'📋',
            '.txt':'📝','.md':'📖','.ipynb':'📓','.rb':'💎','.go':'🐹',
            '.rs':'🦀','.php':'🐘','.java':'☕','.cpp':'⚙️','.c':'⚙️'}.get(e,'📄')

def get_setting(k): 
    r = db_run("SELECT val FROM settings WHERE key=?", (k,), fetch='one')
    return r['val'] if r else None

def set_setting(k,v): db_run("INSERT OR REPLACE INTO settings(key,val) VALUES(?,?)", (k,v))
def maintenance(): return get_setting('maintenance') == '1'

SUPPORTED = {'.py','js','.ts','.sh','.bash','.rb','.go','.php','.java',
             '.cpp','.c','.html','.ipynb','.txt','.json','.md','.env',
             '.zip','.tar','.gz','.rar'}

# ══════════════════════════════════════════════
# USER FUNCTIONS
# ══════════════════════════════════════════════
def save_user(uid, uname, fname, ref=None):
    now = datetime.now().isoformat()
    ex = db_run("SELECT uid FROM users WHERE uid=?", (uid,), fetch='one')
    if ex:
        db_run("UPDATE users SET uname=?,fname=?,last_seen=?,last_active=? WHERE uid=?",
               (uname, fname, now, now, uid))
    else:
        rc = f"REF{uid}{''.join(random.choices(string.ascii_uppercase+string.digits,k=6))}"
        fc = int(get_setting('free_credits') or 3)
        db_run("INSERT INTO users(uid,uname,fname,first_seen,last_seen,last_active,ref_code,credits) VALUES(?,?,?,?,?,?,?,?)",
               (uid, uname, fname, now, now, now, rc, fc))
    if ref:
        db_run("UPDATE users SET referred_by=? WHERE uid=? AND referred_by=0", (ref, uid))

def get_user(uid): return db_run("SELECT * FROM users WHERE uid=?", (uid,), fetch='one')
def is_banned(uid): r=get_user(uid); return bool(r['banned']) if r else False
def is_owner(uid): return uid == OWNER_ID
def is_verified(uid): r=get_user(uid); return bool(r['verified']) if r else False
def set_verified(uid): db_run("UPDATE users SET verified=1 WHERE uid=?", (uid,))
def ban_user(uid): db_run("UPDATE users SET banned=1 WHERE uid=?", (uid,))
def unban_user(uid): db_run("UPDATE users SET banned=0 WHERE uid=?", (uid,))

def is_premium(uid):
    if is_owner(uid): return True
    r = get_user(uid)
    if not r or not r['is_premium']: return False
    if r['premium_expiry']:
        if datetime.fromisoformat(r['premium_expiry']) < datetime.now():
            db_run("UPDATE users SET is_premium=0, premium_expiry=NULL WHERE uid=?", (uid,))
            return False
    return True

def add_premium(uid, dur):
    m = re.match(r'^(\d+)([dmy])$', dur.lower())
    if not m: return False, "Format: 7d / 1m / 1y"
    n,u = int(m.group(1)), m.group(2)
    delta = {'d':timedelta(days=n),'m':timedelta(days=n*30),'y':timedelta(days=n*365)}[u]
    exp = datetime.now()+delta
    db_run("UPDATE users SET is_premium=1, premium_expiry=? WHERE uid=?", (exp.isoformat(), uid))
    return True, exp.strftime("%Y-%m-%d")

def remove_premium(uid): db_run("UPDATE users SET is_premium=0, premium_expiry=NULL WHERE uid=?", (uid,))

def get_credits(uid):
    if is_owner(uid): return 999999
    r = get_user(uid)
    return r['credits'] if r else 0

def add_credits(uid, n): db_run("UPDATE users SET credits=credits+? WHERE uid=?", (n, uid))
def rem_credits(uid, n): db_run("UPDATE users SET credits=MAX(0,credits-?) WHERE uid=?", (n, uid))

def can_run(uid): return is_owner(uid) or is_premium(uid) or get_credits(uid) >= 1

def process_referral(new_uid, code):
    r = db_run("SELECT uid FROM users WHERE ref_code=?", (code,), fetch='one')
    if r and r['uid'] != new_uid:
        db_run("UPDATE users SET credits=credits+5, total_refs=total_refs+1 WHERE uid=?", (r['uid'],))
        db_run("UPDATE users SET referred_by=? WHERE uid=? AND referred_by=0", (r['uid'], new_uid))
        return r['uid']
    return None

def get_user_dir(uid):
    d = FILES / str(uid)
    d.mkdir(parents=True, exist_ok=True)
    return d

# ══════════════════════════════════════════════
# FILE FUNCTIONS
# ══════════════════════════════════════════════
def save_file(uid, fname, fpath, ftype, main=None, size=0, is_zip=0, extract=None):
    return db_run(
        "INSERT INTO files(uid,fname,fpath,ftype,uploaded,main_file,fsize,is_zip,extract_path) VALUES(?,?,?,?,?,?,?,?,?)",
        (uid, fname, fpath, ftype, datetime.now().isoformat(), main, size, is_zip, extract)
    )

def get_file(uid, fid): return db_run("SELECT * FROM files WHERE uid=? AND id=?", (uid, fid), fetch='one')
def get_files(uid): return db_run("SELECT * FROM files WHERE uid=? ORDER BY id DESC", (uid,), fetch='all') or []
def del_file(uid, fid): db_run("DELETE FROM files WHERE uid=? AND id=?", (uid, fid))
def update_main(uid, fid, main): db_run("UPDATE files SET main_file=? WHERE uid=? AND id=?", (main, uid, fid))
def inc_run(fid): db_run("UPDATE files SET run_count=run_count+1 WHERE id=?", (fid,))

# ══════════════════════════════════════════════
# VERIFICATION
# ══════════════════════════════════════════════
COLORS = {
    "🔴 Red":"red","🔵 Blue":"blue","🟢 Green":"green","🟡 Yellow":"yellow",
    "🟠 Orange":"orange","🟣 Purple":"purple","⚫ Black":"black",
    "⚪ White":"white","🟤 Brown":"brown","🌸 Pink":"pink"
}
C_REV = {v:k for k,v in COLORS.items()}

def gen_verify():
    opts = random.sample(list(COLORS.keys()), 4)
    correct = random.choice(opts)
    random.shuffle(opts)
    return COLORS[correct], opts

def save_verify(uid, correct, opts):
    exp = (datetime.now()+timedelta(minutes=5)).isoformat()
    db_run("INSERT OR REPLACE INTO verify(uid,correct,options,expires,tries) VALUES(?,?,?,?,0)",
           (uid, correct, json.dumps(opts), exp))

def check_verify(uid, selected):
    r = db_run("SELECT * FROM verify WHERE uid=?", (uid,), fetch='one')
    if not r: return False,"expired"
    if datetime.fromisoformat(r['expires']) < datetime.now():
        db_run("DELETE FROM verify WHERE uid=?", (uid,))
        return False,"expired"
    db_run("UPDATE verify SET tries=tries+1 WHERE uid=?", (uid,))
    if r['tries'] >= 5: return False,"too_many"
    return selected == r['correct'], r['correct']

def verify_kb(opts):
    kb=[]
    row=[]
    for i,c in enumerate(opts):
        row.append(InlineKeyboardButton(c, callback_data=f"v_{COLORS[c]}"))
        if len(row)==2: kb.append(row); row=[]
    if row: kb.append(row)
    return InlineKeyboardMarkup(kb)

# ══════════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════════
def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📁 "+tb("UPLOAD FILE")), KeyboardButton("🗂 "+tb("MY FILES"))],
        [KeyboardButton("⚡ "+tb("TERMINAL")), KeyboardButton("🔄 "+tb("AUTO RESTART"))],
        [KeyboardButton("📦 "+tb("INSTALL PKG")), KeyboardButton("📋 "+tb("MY PACKAGES"))],
        [KeyboardButton("📊 "+tb("STATUS")), KeyboardButton("🏓 "+tb("PING")), KeyboardButton("🖥 "+tb("CONSOLE"))],
        [KeyboardButton("👤 "+tb("ACCOUNT")), KeyboardButton("💎 "+tb("PREMIUM INFO"))],
        [KeyboardButton("💰 "+tb("BUY CREDITS")), KeyboardButton("🔗 "+tb("REFERRAL"))],
        [KeyboardButton("⚙️ "+tb("ADMIN")), KeyboardButton("📖 "+tb("GUIDE"))],
    ], resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🚫 "+tb("BAN")), KeyboardButton("✅ "+tb("UNBAN"))],
        [KeyboardButton("👥 "+tb("ALL USERS")), KeyboardButton("📊 "+tb("BOT STATS"))],
        [KeyboardButton("⭐ "+tb("ADD PREMIUM")), KeyboardButton("❌ "+tb("DEL PREMIUM"))],
        [KeyboardButton("👑 "+tb("PREMIUM LIST")), KeyboardButton("⌛ "+tb("EXPIRED LIST"))],
        [KeyboardButton("💎 "+tb("ADD COINS")), KeyboardButton("💸 "+tb("REM COINS"))],
        [KeyboardButton("📢 "+tb("BROADCAST")), KeyboardButton("🎁 "+tb("GIVE ALL"))],
        [KeyboardButton("🔧 "+tb("MAINTENANCE")), KeyboardButton("💣 "+tb("KILL ALL"))],
        [KeyboardButton("🏠 "+tb("BACK"))],
    ], resize_keyboard=True)

# ══════════════════════════════════════════════
# GLOBAL STATE
# ══════════════════════════════════════════════
running_procs: dict[str, 'ProcMonitor'] = {}
terminals: dict[int, 'Terminal'] = {}
browsers: dict[str, 'FileBrowser'] = {}
states: dict[int, dict] = {}

def pkey(uid, fname): return f"{uid}::{fname}"

# ══════════════════════════════════════════════
# PROCESS MONITOR
# ══════════════════════════════════════════════
class ProcMonitor:
    def __init__(self, proc, fname, uid, cmd, fid=None):
        self.proc = proc
        self.fname = fname
        self.uid = uid
        self.cmd = cmd
        self.fid = fid
        self.t0 = time.time()
        self.logs = []
        self._lk = threading.Lock()
        self._t = threading.Thread(target=self._read, daemon=True)
        self._t.start()

    def _read(self):
        try:
            for line in iter(self.proc.stdout.readline, ''):
                if line:
                    with self._lk:
                        self.logs.append(line.strip())
                        if len(self.logs) > 500: self.logs = self.logs[-500:]
        except: pass

    def alive(self): return self.proc.poll() is None
    def runtime(self): return fmt_time(time.time()-self.t0)

    def get_logs(self, n=20):
        with self._lk: return list(self.logs[-n:])

    def stop(self):
        try: self.proc.terminate(); self.proc.wait(timeout=5)
        except:
            try: self.proc.kill()
            except: pass

    def mem_usage(self):
        try:
            p = psutil.Process(self.proc.pid)
            return fmt_bytes(p.memory_info().rss)
        except: return "N/A"

    def cpu_usage(self):
        try:
            p = psutil.Process(self.proc.pid)
            return f"{p.cpu_percent(interval=0.1):.1f}%"
        except: return "N/A"

# ══════════════════════════════════════════════
# TERMINAL
# ══════════════════════════════════════════════
class Terminal:
    def __init__(self, uid, chat_id, bot, cwd=None):
        self.uid = uid
        self.chat_id = chat_id
        self.bot = bot
        self.cwd = str(cwd or get_user_dir(uid))
        self.proc = None
        self.lines = []
        self.running = False
        self.msg_id = None
        self._rt = None
        self._rr = None
        self.waiting = False
        self.prompt = ""
        self.termux = False

    def display(self):
        lines = self.lines[-20:] if self.lines else ["$ Ready"]
        t = f"╭──〔 ⚡ {tb('VPS TERMINAL')} ⚡ 〕──╮\n"
        for l in lines:
            t += f"│ {l.strip().replace('`',chr(39))[:55]}\n"
        if self.running:
            t += f"│\n│ {'📝 '+self.prompt if self.waiting else '⏳ Running...'}\n"
        else:
            t += f"│\n│ 📂 ...{self.cwd[-25:]}\n│ $ _\n"
        t += "╰──────────────────────────────╯"
        return t

    def kb(self):
        if self.termux:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("ESC",callback_data="tk_esc"),
                 InlineKeyboardButton("TAB",callback_data="tk_tab"),
                 InlineKeyboardButton("↑",callback_data="tk_up"),
                 InlineKeyboardButton("↓",callback_data="tk_dn")],
                [InlineKeyboardButton("CTRL+C",callback_data="tk_cc"),
                 InlineKeyboardButton("CTRL+Z",callback_data="tk_cz"),
                 InlineKeyboardButton("CTRL+D",callback_data="tk_cd"),
                 InlineKeyboardButton("CTRL+L",callback_data="tk_cl")],
                [InlineKeyboardButton("/",callback_data="tk_sl"),
                 InlineKeyboardButton("-",callback_data="tk_ds"),
                 InlineKeyboardButton("~",callback_data="tk_tl"),
                 InlineKeyboardButton("⌫",callback_data="tk_bs")],
                [InlineKeyboardButton("🔙 Back",callback_data="tk_back")],
            ])
        if self.running:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh",callback_data="t_ref"),
                 InlineKeyboardButton("📤 Input",callback_data="t_inp")],
                [InlineKeyboardButton("⏹ Stop",callback_data="t_stop"),
                 InlineKeyboardButton("🔴 Kill",callback_data="t_kill")],
                [InlineKeyboardButton("⌨️ Keys",callback_data="t_txkb")],
            ])
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🐍 Python",callback_data="t_py"),
             InlineKeyboardButton("🟨 Node",callback_data="t_nd"),
             InlineKeyboardButton("📜 Bash",callback_data="t_sh")],
            [InlineKeyboardButton("📦 Pip",callback_data="t_pip"),
             InlineKeyboardButton("⚡ CMD",callback_data="t_cmd"),
             InlineKeyboardButton("📂 LS",callback_data="t_ls")],
            [InlineKeyboardButton("📁 PWD",callback_data="t_pwd"),
             InlineKeyboardButton("🏠 Home",callback_data="t_home"),
             InlineKeyboardButton("🧹 Clear",callback_data="t_cl")],
            [InlineKeyboardButton("⌨️ Termux KB",callback_data="t_txkb"),
             InlineKeyboardButton("🔴 Close",callback_data="t_close")],
        ])

    async def run(self, cmd):
        if self.running: self.lines.append("⚠️ Already running!"); return
        self.lines.append(f"$ {cmd[:70]}")
        self.running = True
        try:
            self.proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.PIPE,
                cwd=self.cwd,
                executable='/bin/bash' if Path('/bin/bash').exists() else None
            )
            self._rr = asyncio.create_task(self._reader())
            self._rt = asyncio.create_task(self._refresher())
        except Exception as e:
            self.lines.append(f"❌ {e}"); self.running = False

    async def _reader(self):
        kw=['enter','input','phone','number',':','?','>','password','otp','select','choice']
        try:
            while self.running and self.proc:
                try:
                    line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=0.5)
                    if not line: break
                    d = line.decode('utf-8', errors='ignore').rstrip()
                    if d:
                        self.lines.append(d)
                        if len(self.lines)>500: self.lines=self.lines[-500:]
                        if any(k in d.lower() for k in kw) and not self.waiting:
                            self.waiting=True; self.prompt="Waiting for input..."
                except asyncio.TimeoutError: continue
                except: break
            if self.proc:
                await self.proc.wait()
                rc = self.proc.returncode
                self.lines.append(f"{'✅' if rc==0 else '❌'} Exit: {rc}")
                self.proc = None
            self.running=False; self.waiting=False
            if self._rt: self._rt.cancel()
            await self._upd()
        except Exception as e:
            self.lines.append(f"❌ {e}"); self.running=False

    async def _refresher(self):
        try:
            while self.running:
                await asyncio.sleep(2.5); await self._upd()
        except asyncio.CancelledError: pass

    async def _upd(self):
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id, message_id=self.msg_id,
                text=self.display(), reply_markup=self.kb()
            )
        except: pass

    async def send_input(self, txt):
        if self.proc and self.running:
            try:
                self.proc.stdin.write((txt+'\n').encode())
                await self.proc.stdin.drain()
                self.lines.append(f"📤 {txt}")
                self.waiting=False
                await self._upd(); return True
            except: pass
        return False

    async def stop_proc(self):
        if self.proc:
            try:
                self.proc.terminate()
                await asyncio.sleep(1)
                if self.proc.returncode is None: self.proc.kill()
            except: pass
        self.running=False; self.waiting=False
        self.lines.append("⏹ Stopped")
        for t in [self._rt,self._rr]:
            if t: t.cancel()
        await self._upd()

    async def kill_proc(self):
        if self.proc:
            try: self.proc.kill()
            except: pass
        self.running=False; self.waiting=False
        self.lines.append("🔴 Killed")
        for t in [self._rt,self._rr]:
            if t: t.cancel()
        await self._upd()

# ══════════════════════════════════════════════
# FILE BROWSER
# ══════════════════════════════════════════════
class FileBrowser:
    def __init__(self, uid, base, fid):
        self.uid=uid; self.base=Path(base)
        self.cur=Path(base); self.fid=fid
        self.msg_id=None; self._map={}

    def items(self):
        try:
            out=[]
            for p in sorted(self.cur.iterdir(), key=lambda x:(not x.is_dir(),x.name.lower())):
                rel=str(p.relative_to(self.base))
                h=hashlib.md5(rel.encode()).hexdigest()[:8]
                self._map[h]=p; out.append((p.is_dir(),p.name,h))
            return out
        except: return []

    def display(self):
        rel=str(self.cur.relative_to(self.base)) if self.cur!=self.base else 'Root'
        items=self.items()
        t=f"╭──〔 📂 {rel[:30]} 〕──╮\n│\n"
        if not items: t+="│  (Empty)\n"
        for is_dir,name,_ in items[:15]:
            t+=f"│  {'📁' if is_dir else file_icon(name)} {name[:38]}\n"
        if len(items)>15: t+=f"│  ... +{len(items)-15} more\n"
        t+="╰──────────────────────────╯"
        return t

    def kb(self):
        items=self.items(); kb=[]
        for is_dir,name,h in items[:12]:
            icon="📁" if is_dir else file_icon(name)
            cb=f"br_d_{h}" if is_dir else f"br_f_{h}"
            kb.append([InlineKeyboardButton(f"{icon} {name[:30]}",callback_data=cb)])
        nav=[]
        if self.cur!=self.base: nav.append(InlineKeyboardButton("⬆️ Up",callback_data="br_up"))
        nav.append(InlineKeyboardButton("🏠 Root",callback_data="br_root"))
        nav.append(InlineKeyboardButton("🔙 Back",callback_data=f"file_{self.fid}"))
        kb.append(nav)
        return InlineKeyboardMarkup(kb)

# ══════════════════════════════════════════════
# PYTHON PREPARER
# ══════════════════════════════════════════════
def prepare_py(fp):
    try:
        content = Path(fp).read_text(encoding='utf-8', errors='ignore')
        lines = ["# -*- coding: utf-8 -*-","import sys,os,subprocess",""]
        for line in content.split('\n'):
            s=line.lstrip(); ind=line[:len(line)-len(s)]
            if s.startswith('!pip '):
                pkg=s.split()[-1]
                lines.append(f"{ind}subprocess.run([sys.executable,'-m','pip','install','{pkg}','-q'],capture_output=True)")
            elif s.startswith('!apt') or s.startswith('!sudo'):
                lines.append(f"{ind}# skip: {s}")
            elif s.startswith('!'):
                lines.append(f"{ind}subprocess.run({repr(s[1:].strip())},shell=True)")
            else:
                lines.append(line)
        out=str(fp)+'.__run__.py'
        Path(out).write_text('\n'.join(lines), encoding='utf-8')
        return out
    except: return fp

def get_cmd(fp):
    e=Path(fp).suffix.lower()
    return {
        '.py':[sys.executable,'-u',fp],
        '.js':['node',fp],'.ts':['ts-node',fp],
        '.sh':['bash',fp],'.bash':['bash',fp],
        '.rb':['ruby',fp],'.go':['go','run',fp],
        '.php':['php',fp],'.r':['Rscript',fp],
    }.get(e)

# ══════════════════════════════════════════════
# FILE DETAIL UI
# ══════════════════════════════════════════════
async def show_file(msg_or_query, uid, fid, edit=True):
    fi = get_file(uid, fid)
    if not fi:
        txt="❌ File not found"; kb=None
    else:
        fp = fi['main_file'] or fi['fpath']
        fname = fi['fname']
        key = pkey(uid, Path(fp).name)
        mon = running_procs.get(key)
        alive = mon and mon.alive()
        status = "🟢 RUNNING" if alive else "🔴 STOPPED"
        runtime = mon.runtime() if alive else "—"
        mem = mon.mem_usage() if alive else "—"
        cpu_u = mon.cpu_usage() if alive else "—"

        txt = f"""╭────〔 {file_icon(fname)} {tb('FILE DETAILS')} 〕────╮
│
│  📁 {tb('Name:')} {fname}
│  📊 {tb('Status:')} {status}
│  ⏱️ {tb('Runtime:')} {runtime}
│  🧠 {tb('Memory:')} {mem}
│  💻 {tb('CPU:')} {cpu_u}
│  📏 {tb('Size:')} {fmt_bytes(fi['fsize'] or 0)}
│  🔢 {tb('Runs:')} {fi['run_count'] or 0}
│  📅 {tb('Uploaded:')} {(fi['uploaded'] or '')[:10]}
│
╰──────────────────────────────────╯"""
        kb_rows = [
            [InlineKeyboardButton("▶️ "+tb("START"), callback_data=f"start_{fid}"),
             InlineKeyboardButton("⏹ "+tb("STOP"), callback_data=f"stop_{fid}")],
            [InlineKeyboardButton("📋 "+tb("LOGS"), callback_data=f"logs_{fid}"),
             InlineKeyboardButton("🔄 "+tb("RESTART"), callback_data=f"rst_{fid}")],
            [InlineKeyboardButton("🗑 "+tb("DELETE"), callback_data=f"del_{fid}"),
             InlineKeyboardButton("🔃 "+tb("REFRESH"), callback_data=f"file_{fid}")],
        ]
        if fi['is_zip'] and fi['extract_path'] and Path(fi['extract_path']).exists():
            kb_rows.append([InlineKeyboardButton("📂 Browse ZIP Files", callback_data=f"browse_{fid}")])
        kb = InlineKeyboardMarkup(kb_rows)

    if edit:
        await msg_or_query.edit_message_text(txt, reply_markup=kb)
    else:
        await msg_or_query.reply_text(txt, reply_markup=kb)

# ══════════════════════════════════════════════
# START PROCESS
# ══════════════════════════════════════════════
async def do_start(q, uid, fid, ctx):
    if not can_run(uid):
        await q.edit_message_text(
            f"❌ {tb('NO CREDITS!')}\n\n"
            f"💰 Your credits: {get_credits(uid)}\n"
            f"🔗 Refer friends to earn +5 credits!\n"
            f"💎 Or buy credits from owner"
        ); return

    # Check process limit
    user_procs = [k for k in running_procs if k.startswith(f"{uid}::") and running_procs[k].alive()]
    max_p = MAX_PROC_PREMIUM if (is_owner(uid) or is_premium(uid)) else MAX_PROC_FREE
    if len(user_procs) >= max_p and not is_owner(uid):
        await q.edit_message_text(
            f"❌ {tb('PROCESS LIMIT REACHED!')}\n\n"
            f"⚡ Running: {len(user_procs)}/{max_p}\n"
            f"⭐ Premium users get {MAX_PROC_PREMIUM} processes!"
        ); return

    fi = get_file(uid, fid)
    if not fi:
        await q.edit_message_text("❌ File not found"); return

    fp = fi['main_file'] or fi['fpath']
    fname = Path(fp).name
    key = pkey(uid, fname)

    # Stop existing
    if key in running_procs and running_procs[key].alive():
        running_procs[key].stop(); del running_procs[key]

    # Handle notebook
    ext = Path(fp).suffix.lower()
    if ext == '.ipynb' and NOTEBOOK_SUPPORT:
        await q.edit_message_text(f"📓 {tb('RUNNING NOTEBOOK...')}")
        try:
            nb = nbformat.read(open(fp), as_version=4)
            ep = ExecutePreprocessor(timeout=600, kernel_name='python3')
            ep.preprocess(nb, {'metadata':{'path':str(Path(fp).parent)}})
            await q.edit_message_text(f"✅ {tb('NOTEBOOK DONE!')}")
        except Exception as e:
            await q.edit_message_text(f"❌ Notebook error:\n{str(e)[:500]}")
        return

    # Get command
    if ext == '.py':
        actual = prepare_py(fp)
        cmd = [sys.executable, '-u', actual]
    else:
        cmd = get_cmd(fp)
        if not cmd:
            await q.edit_message_text(f"❌ Cannot run {ext} files"); return

    await q.edit_message_text(f"⚙️ {tb('STARTING...')}\n📄 {fname}")

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=str(Path(fp).parent),
            env={**os.environ, 'PYTHONUNBUFFERED':'1'}
        )
        await asyncio.sleep(2)

        if proc.poll() is not None:
            out = proc.stdout.read()
            await q.edit_message_text(
                f"❌ {tb('PROCESS CRASHED!')}\n\n```\n{out[-1000:]}\n```",
                parse_mode=ParseMode.MARKDOWN
            ); return

        mon = ProcMonitor(proc, fname, uid, cmd, fid)
        running_procs[key] = mon
        inc_run(fid)
        db_run("UPDATE users SET total_runs=total_runs+1 WHERE uid=?", (uid,))

        if not is_owner(uid) and not is_premium(uid):
            rem_credits(uid, 1)
            asyncio.create_task(credit_watchdog(uid, key, ctx))

        r = get_user(uid)
        if r and r['auto_restart']:
            asyncio.create_task(auto_restart(uid, fid, fp, cmd, key))

        credits_left = get_credits(uid) if not is_owner(uid) else "♾️"
        await q.edit_message_text(
            f"🚀 {tb('STARTED!')}\n"
            f"📄 {fname}\n"
            f"💰 Credits: {credits_left}\n"
            f"⚡ Running processes: {len([k for k in running_procs if k.startswith(f'{uid}::') and running_procs[k].alive()])}"
        )
    except Exception as e:
        await q.edit_message_text(f"❌ Error: {e}")

async def credit_watchdog(uid, key, ctx):
    await asyncio.sleep(1200)
    if key in running_procs and running_procs[key].alive():
        if get_credits(uid) >= 1:
            rem_credits(uid, 1)
            asyncio.create_task(credit_watchdog(uid, key, ctx))
        else:
            if key in running_procs:
                running_procs[key].stop(); del running_procs[key]
            try: await ctx.bot.send_message(uid, f"⚠️ {tb('CREDITS FINISHED!')} Process stopped.")
            except: pass

async def auto_restart(uid, fid, fp, cmd, key):
    while True:
        await asyncio.sleep(10)
        r = get_user(uid)
        if not r or not r['auto_restart']: break
        if key not in running_procs or not running_procs[key].alive():
            if not can_run(uid): break
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, cwd=str(Path(fp).parent),
                    env={**os.environ,'PYTHONUNBUFFERED':'1'}
                )
                running_procs[key] = ProcMonitor(proc, Path(fp).name, uid, cmd, fid)
                if not is_owner(uid) and not is_premium(uid): rem_credits(uid, 1)
            except: break

# ══════════════════════════════════════════════
# PACKAGE INSTALLER
# ══════════════════════════════════════════════
async def pip_install(pkg, msg, uid):
    logs=[]
    async def upd():
        try:
            shown=logs[-10:] if logs else ["Starting..."]
            t=f"╭──〔 📦 {tb('INSTALLING')} 〕──╮\n"
            t+="\n".join(f"│ {l[:52]}" for l in shown)
            t+="\n╰──────────────────────────╯"
            await msg.edit_text(t)
        except: pass

    async def run():
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,'-m','pip','install',pkg,'--no-warn-script-location',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            logs.append(f"pip install {pkg}"); await upd()
            while True:
                try:
                    line = await asyncio.wait_for(proc.stdout.readline(), timeout=120)
                    if not line: break
                    d=line.decode().strip()
                    if d: logs.append(d); await upd()
                except asyncio.TimeoutError:
                    logs.append("Still installing..."); await upd()
            await proc.wait()
            if proc.returncode==0:
                db_run("INSERT OR REPLACE INTO packages(uid,pkg,installed) VALUES(?,?,?)",
                       (uid, pkg, datetime.now().isoformat()))
                await msg.edit_text(f"✅ {tb('INSTALLED:')} {pkg}\n\nYou can now use `import {pkg}` in your scripts!", parse_mode=ParseMode.MARKDOWN)
            else:
                await msg.edit_text(f"❌ {tb('FAILED:')} {pkg}\nCheck the package name and try again.")
        except Exception as e:
            await msg.edit_text(f"❌ Error: {e}")

    asyncio.create_task(run())

# ══════════════════════════════════════════════
# /start HANDLER
# ══════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u=update.effective_user; uid=u.id
    if is_banned(uid):
        kb=[[InlineKeyboardButton("📩 Appeal",url=f"https://t.me/{SUPPORT_USER}")]]
        await update.message.reply_text(f"🚫 {tb('YOU ARE BANNED')}",reply_markup=InlineKeyboardMarkup(kb)); return
    if maintenance() and not is_owner(uid):
        await update.message.reply_text(f"🔧 {tb('MAINTENANCE MODE')}\nPlease try later."); return

    ref=None
    if ctx.args and ctx.args[0].startswith('REF'):
        ref=process_referral(uid, ctx.args[0])

    save_user(uid, u.username or '', u.first_name or '', ref)

    if ref:
        try: await ctx.bot.send_message(ref, f"🎉 {tb('NEW REFERRAL!')} +5 Credits!")
        except: pass

    if not is_verified(uid):
        c,opts=gen_verify(); save_verify(uid,c,opts)
        cname=C_REV.get(c,c)
        await update.message.reply_text(
            f"🔐 {tb('VERIFICATION')}\n\nSelect: {cname}\n⏰ 5 minutes",
            reply_markup=verify_kb(opts)); return

    await show_welcome(update, uid)

async def show_welcome(update, uid):
    u=update.effective_user
    procs=[k for k in running_procs if k.startswith(f"{uid}::") and running_procs[k].alive()]
    files=get_files(uid)
    if is_owner(uid): cr,st="♾️","👑 Owner"
    else: cr=str(get_credits(uid)); st="⭐ Premium" if is_premium(uid) else "🆓 Free"
    max_p=MAX_PROC_PREMIUM if is_premium(uid) else MAX_PROC_FREE

    await update.message.reply_text(f"""╭────〔 🌺 {tb("ULTRA VPS BOT")} 🌺 〕────╮
│
│  👋 {tb("Welcome")}, {u.first_name}!
│
│  💰 {tb("Credits:")} {cr}
│  👑 {tb("Status:")} {st}
│  📁 {tb("Files:")} {len(files)}
│  ⚡ {tb("Running:")} {len(procs)}/{max_p}
│
│  🔗 Refer → +5 Credits each
│  ⏱️ 1 Credit = 20 min runtime
│  📦 Run multiple files at once!
│
╰──────────────────────────────────╯""", reply_markup=main_kb())

# ══════════════════════════════════════════════
# DOCUMENT HANDLER
# ══════════════════════════════════════════════
async def handle_doc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    if is_banned(uid) or (maintenance() and not is_owner(uid)): return

    doc=update.message.document
    fname=doc.file_name or "file"
    fsize=doc.file_size or 0
    ext=Path(fname).suffix.lower()
    max_sz=MAX_SIZE_PREMIUM if (is_owner(uid) or is_premium(uid)) else MAX_SIZE_FREE

    if fsize>max_sz:
        await update.message.reply_text(
            f"❌ {tb('TOO LARGE!')}\n📏 Max: {fmt_bytes(max_sz)}\n⭐ Premium: {fmt_bytes(MAX_SIZE_PREMIUM)}"); return

    if ext not in SUPPORTED and ext not in {'.zip','.tar','.gz','.rar'}:
        await update.message.reply_text(f"❌ Unsupported: {ext}\n✅ Supported: .py .js .ts .sh .rb .go .php .zip .tar + more"); return

    msg=await update.message.reply_text(f"⏳ {tb('DOWNLOADING...')} ({fmt_bytes(fsize)})")
    udir=get_user_dir(uid); fpath=udir/fname

    try:
        tf=await doc.get_file()
        await tf.download_to_drive(str(fpath))
    except Exception as e:
        await msg.edit_text(f"❌ Download failed: {e}"); return

    # ZIP
    if ext=='.zip':
        try:
            ex_dir=fpath.parent/fpath.stem; ex_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(str(fpath),'r') as z: z.extractall(str(ex_dir))
            fid=save_file(uid,fname,str(fpath),'zip',None,fsize,1,str(ex_dir))
            browser=FileBrowser(uid,str(ex_dir),fid)
            browsers[f"{uid}_{fid}"]=browser
            browser.msg_id=msg.message_id
            await msg.edit_text(browser.display(),reply_markup=browser.kb())
            return
        except Exception as e:
            await msg.edit_text(f"❌ ZIP error: {e}"); return

    # TAR/GZ
    if ext in {'.tar','.gz'}:
        try:
            stem=fname.replace('.tar.gz','').replace('.tar','').replace('.gz','')
            ex_dir=fpath.parent/stem; ex_dir.mkdir(exist_ok=True)
            with tarfile.open(str(fpath)) as tf2: tf2.extractall(str(ex_dir))
            fid=save_file(uid,fname,str(fpath),'archive',None,fsize,1,str(ex_dir))
            browser=FileBrowser(uid,str(ex_dir),fid)
            browsers[f"{uid}_{fid}"]=browser
            browser.msg_id=msg.message_id
            await msg.edit_text(browser.display(),reply_markup=browser.kb())
            return
        except Exception as e:
            await msg.edit_text(f"❌ Archive error: {e}"); return

    ftype={'py':'python','js':'javascript','ts':'typescript','sh':'shell',
           'rb':'ruby','go':'go','php':'php','html':'web','ipynb':'notebook'}.get(ext.lstrip('.'),'text')
    fid=save_file(uid,fname,str(fpath),ftype,None,fsize)
    await show_file(msg, uid, fid)

# ══════════════════════════════════════════════
# CALLBACK HANDLER
# ══════════════════════════════════════════════
async def handle_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; uid=q.from_user.id; data=q.data
    if is_banned(uid): await q.answer("Banned!"); return
    await q.answer()

    # Verify
    if data.startswith("v_"):
        sel=data[2:]
        ok,info=check_verify(uid,sel)
        if info=="expired": await q.edit_message_text("⏰ Expired! /start again"); return
        if info=="too_many": await q.edit_message_text("🚫 Too many tries! /start again"); return
        if ok:
            set_verified(uid)
            db_run("DELETE FROM verify WHERE uid=?", (uid,))
            await q.edit_message_text(f"✅ {tb('VERIFIED!')} Welcome!")
            await q.message.reply_text("🎉 Use buttons below!", reply_markup=main_kb())
        else:
            await q.edit_message_text(f"❌ Wrong! Correct: {C_REV.get(info,info)}\n/start again")
        return

    # File detail
    if data.startswith("file_"):
        await show_file(q, uid, int(data[5:])); return

    # Browse ZIP
    if data.startswith("browse_"):
        fid=int(data[7:]); fi=get_file(uid,fid)
        if fi and fi['extract_path'] and Path(fi['extract_path']).exists():
            b=FileBrowser(uid,fi['extract_path'],fid)
            b.msg_id=q.message.message_id
            browsers[f"{uid}_{fid}"]=b
            await q.edit_message_text(b.display(),reply_markup=b.kb())
        return

    # Browser nav
    if data.startswith("br_"):
        bk=next((k for k,b in browsers.items() if k.startswith(f"{uid}_") and b.msg_id==q.message.message_id), None)
        b=browsers.get(bk)
        if not b: await q.edit_message_text("❌ Session expired"); return
        if data=="br_up":
            if b.cur!=b.base: b.cur=b.cur.parent
        elif data=="br_root":
            b.cur=b.base
        elif data.startswith("br_d_"):
            p=b._map.get(data[5:])
            if p and p.is_dir(): b.cur=p
        elif data.startswith("br_f_"):
            p=b._map.get(data[5:])
            if p:
                update_main(uid, b.fid, str(p))
                await q.edit_message_text(f"✅ {tb('MAIN FILE SET!')}\n📄 {p.name}")
                browsers.pop(bk,None); return
        await q.edit_message_text(b.display(),reply_markup=b.kb()); return

    # Process actions
    if data.startswith("start_"): await do_start(q,uid,int(data[6:]),ctx); return
    if data.startswith("stop_"):
        fi=get_file(uid,int(data[5:]))
        if fi:
            fp=fi['main_file'] or fi['fpath']; k=pkey(uid,Path(fp).name)
            if k in running_procs: running_procs[k].stop(); del running_procs[k]
            await q.edit_message_text(f"⏹ {tb('STOPPED:')} {fi['fname']}")
        return
    if data.startswith("rst_"):
        fi=get_file(uid,int(data[4:]))
        if fi:
            fp=fi['main_file'] or fi['fpath']; k=pkey(uid,Path(fp).name)
            if k in running_procs: running_procs[k].stop(); del running_procs[k]
            await do_start(q,uid,int(data[4:]),ctx)
        return
    if data.startswith("logs_"):
        fid=int(data[5:]); fi=get_file(uid,fid)
        if fi:
            fp=fi['main_file'] or fi['fpath']; k=pkey(uid,Path(fp).name)
            mon=running_procs.get(k)
            if not mon: await q.edit_message_text("❌ Not running"); return
            logs=mon.get_logs(18)
            lt="\n│  ".join(logs) if logs else "No output yet..."
            await q.edit_message_text(
                f"╭──〔 📋 {tb('LOGS')} 〕──╮\n│\n│  {lt}\n│\n╰──────────────────────────╯",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Refresh",callback_data=f"logs_{fid}"),
                    InlineKeyboardButton("🔙 Back",callback_data=f"file_{fid}")
                ]])
            )
        return
    if data.startswith("del_"):
        fid=int(data[4:]); fi=get_file(uid,fid)
        if fi:
            fp=fi['main_file'] or fi['fpath']; k=pkey(uid,Path(fp).name)
            if k in running_procs: running_procs[k].stop(); del running_procs[k]
            for p in [Path(fi['fpath']), Path(fi['extract_path'] or '')]:
                try:
                    if p.is_file(): p.unlink(missing_ok=True)
                    elif p.is_dir(): shutil.rmtree(p,ignore_errors=True)
                except: pass
            Path(str(fi['fpath'])+'.__run__.py').unlink(missing_ok=True)
            del_file(uid,fid)
            await q.edit_message_text(f"🗑 {tb('DELETED:')} {fi['fname']}")
        return

    # Terminal
    if data.startswith("t_") or data.startswith("tk_"):
        await term_cb(q,uid,data,ctx); return

async def term_cb(q, uid, data, ctx):
    term=terminals.get(uid)
    if not term:
        await q.edit_message_text("❌ Terminal expired. Use Terminal button."); return

    if data=="t_close":
        if term.running: await term.stop_proc()
        terminals.pop(uid,None); states.pop(uid,None)
        await q.message.edit_text("🔴 Terminal closed"); return
    elif data=="t_ref":
        await q.edit_message_text(term.display(),reply_markup=term.kb())
    elif data=="t_stop": await term.stop_proc()
    elif data=="t_kill": await term.kill_proc()
    elif data=="t_cl": term.lines=[]; await q.edit_message_text(term.display(),reply_markup=term.kb())
    elif data=="t_ls":
        r=subprocess.run("ls -la",shell=True,cwd=term.cwd,capture_output=True,text=True)
        term.lines.extend(r.stdout.strip().split('\n')[-15:])
        await q.edit_message_text(term.display(),reply_markup=term.kb())
    elif data=="t_pwd":
        term.lines.append(f"📂 {term.cwd}")
        await q.edit_message_text(term.display(),reply_markup=term.kb())
    elif data=="t_home":
        term.cwd=str(get_user_dir(uid)); term.lines.append(f"📂 {term.cwd}")
        await q.edit_message_text(term.display(),reply_markup=term.kb())
    elif data=="t_txkb":
        term.termux=not term.termux
        await q.edit_message_text(term.display(),reply_markup=term.kb())
    elif data in ["t_py","t_nd","t_sh","t_cmd","t_inp","t_pip"]:
        m,p={"t_py":("py","🐍 Python code:"),"t_nd":("nd","🟨 Node.js code:"),
             "t_sh":("sh","📜 Bash command:"),"t_cmd":("cmd","⚡ Any command:"),
             "t_inp":("inp","📤 Input to process:"),"t_pip":("pip","📦 Package name:")}[data]
        term.waiting=True; term.prompt=p
        states[uid]={'tm':m}
        await q.edit_message_text(term.display(),reply_markup=term.kb())
    elif data.startswith("tk_"):
        k=data[3:]
        if k=="cc" and term.proc:
            try: term.proc.send_signal(2); term.lines.append("^C")
            except: pass
        elif k=="cz" and term.proc:
            try: term.proc.send_signal(20); term.lines.append("^Z")
            except: pass
        elif k=="cd" and term.proc:
            try:
                term.proc.stdin.write(b'\x04')
                await term.proc.stdin.drain()
                term.lines.append("^D")
            except: pass
        elif k=="cl": term.lines=[]
        elif k=="back": term.termux=False
        elif k in ["sl","ds","tl"]: term.lines.append({"sl":"/","ds":"-","tl":"~"}[k])
        await q.edit_message_text(term.display(),reply_markup=term.kb())

# ══════════════════════════════════════════════
# MESSAGE HANDLER
# ══════════════════════════════════════════════
async def handle_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id; txt=update.message.text or ""
    if is_banned(uid): return
    if maintenance() and not is_owner(uid):
        await update.message.reply_text(f"🔧 {tb('MAINTENANCE')}"); return

    st=states.get(uid,{})

    # Terminal input
    if 'tm' in st:
        term=terminals.get(uid); m=st.pop('tm'); states[uid]=st
        if term and m:
            try: await update.message.delete()
            except: pass
            if m=="py": await term.run(f"{sys.executable} -c '{txt.replace(chr(39),chr(39)+chr(92)+chr(39)+chr(39))}'")
            elif m=="nd": await term.run(f"node -e '{txt}'")
            elif m in ["sh","cmd"]: await term.run(txt)
            elif m=="inp":
                if term.running: await term.send_input(txt)
                else: await term.run(txt)
            elif m=="pip":
                term.waiting=False
                msg=await update.effective_chat.send_message(f"📦 Installing {txt}...")
                await pip_install(txt.strip(), msg, uid)
            return

    # Waiting states
    if st.get('pkg'): states.pop(uid,None); msg=await update.message.reply_text(f"📦 Installing {txt}..."); await pip_install(txt.strip(),msg,uid); return
    if st.get('ban'): states.pop(uid,None); ban_user(int(txt.strip())); await update.message.reply_text(f"✅ Banned: {mn(txt.strip())}", parse_mode=ParseMode.MARKDOWN); return
    if st.get('unban'): states.pop(uid,None); unban_user(int(txt.strip())); await update.message.reply_text(f"✅ Unbanned: {mn(txt.strip())}", parse_mode=ParseMode.MARKDOWN); return
    if st.get('ac'):
        states.pop(uid,None)
        p=txt.strip().split(); add_credits(int(p[0]),int(p[1]))
        await update.message.reply_text(f"✅ Added {p[1]} coins to {mn(p[0])}", parse_mode=ParseMode.MARKDOWN)
        try: await ctx.bot.send_message(int(p[0]),f"💰 You received {p[1]} credits!")
        except: pass
        return
    if st.get('rc'): states.pop(uid,None); p=txt.strip().split(); rem_credits(int(p[0]),int(p[1])); await update.message.reply_text(f"✅ Removed {p[1]} coins from {mn(p[0])}", parse_mode=ParseMode.MARKDOWN); return
    if st.get('ap'):
        states.pop(uid,None); p=txt.strip().split(); ok,res=add_premium(int(p[0]),p[1])
        if ok:
            await update.message.reply_text(f"✅ Premium added! Expires: {res}")
            try: await ctx.bot.send_message(int(p[0]),f"⭐ You are PREMIUM! Expires: {res}")
            except: pass
        else: await update.message.reply_text(f"❌ {res}")
        return
    if st.get('rp'): states.pop(uid,None); remove_premium(int(txt.strip())); await update.message.reply_text(f"✅ Premium removed"); return
    if st.get('bc'):
        states.pop(uid,None)
        users=db_run("SELECT uid FROM users WHERE banned=0",fetch='all') or []
        msg=await update.message.reply_text(f"📤 Broadcasting to {len(users)} users...")
        ok=fail=0
        for row in users:
            try: await ctx.bot.send_message(row['uid'],f"📢 {tb('ANNOUNCEMENT')}\n\n{txt}"); ok+=1; await asyncio.sleep(0.3)
            except: fail+=1
        await msg.edit_text(f"✅ Sent: {ok} | Failed: {fail}")
        return
    if st.get('ga'):
        states.pop(uid,None); n=int(txt.strip())
        db_run("UPDATE users SET credits=credits+? WHERE banned=0",(n,))
        c=db_run("SELECT COUNT(*) as c FROM users WHERE banned=0",fetch='one')['c']
        await update.message.reply_text(f"🎁 Gave {n} credits to {c} users!")
        return

    # Buttons
    BTN={
        "📁 "+tb("UPLOAD FILE"): btn_upload,
        "🗂 "+tb("MY FILES"): btn_files,
        "⚡ "+tb("TERMINAL"): btn_terminal,
        "🔄 "+tb("AUTO RESTART"): btn_ar,
        "📦 "+tb("INSTALL PKG"): btn_pkg,
        "📋 "+tb("MY PACKAGES"): btn_pkgs,
        "📊 "+tb("STATUS"): btn_status,
        "🏓 "+tb("PING"): btn_ping,
        "🖥 "+tb("CONSOLE"): btn_console,
        "👤 "+tb("ACCOUNT"): btn_account,
        "💎 "+tb("PREMIUM INFO"): btn_premium,
        "💰 "+tb("BUY CREDITS"): btn_credits,
        "🔗 "+tb("REFERRAL"): btn_ref,
        "⚙️ "+tb("ADMIN"): btn_admin,
        "📖 "+tb("GUIDE"): btn_guide,
        # Admin
        "🚫 "+tb("BAN"): lambda u,c: (states.__setitem__(u.effective_user.id,{'ban':True}), u.message.reply_text("🚫 Send user ID:"))[-1],
        "✅ "+tb("UNBAN"): lambda u,c: (states.__setitem__(u.effective_user.id,{'unban':True}), u.message.reply_text("✅ Send user ID:"))[-1],
        "👥 "+tb("ALL USERS"): btn_all_users,
        "📊 "+tb("BOT STATS"): btn_stats,
        "⭐ "+tb("ADD PREMIUM"): lambda u,c: (states.__setitem__(u.effective_user.id,{'ap':True}), u.message.reply_text("⭐ Format: user_id 30d"))[-1],
        "❌ "+tb("DEL PREMIUM"): lambda u,c: (states.__setitem__(u.effective_user.id,{'rp':True}), u.message.reply_text("❌ Send user ID:"))[-1],
        "👑 "+tb("PREMIUM LIST"): btn_prem_list,
        "⌛ "+tb("EXPIRED LIST"): btn_exp_list,
        "💎 "+tb("ADD COINS"): lambda u,c: (states.__setitem__(u.effective_user.id,{'ac':True}), u.message.reply_text("💎 Format: user_id amount"))[-1],
        "💸 "+tb("REM COINS"): lambda u,c: (states.__setitem__(u.effective_user.id,{'rc':True}), u.message.reply_text("💸 Format: user_id amount"))[-1],
        "📢 "+tb("BROADCAST"): lambda u,c: (states.__setitem__(u.effective_user.id,{'bc':True}), u.message.reply_text("📢 Send message:"))[-1],
        "🎁 "+tb("GIVE ALL"): lambda u,c: (states.__setitem__(u.effective_user.id,{'ga':True}), u.message.reply_text("🎁 Amount to give all:"))[-1],
        "🔧 "+tb("MAINTENANCE"): btn_maintenance,
        "💣 "+tb("KILL ALL"): btn_kill_all,
        "🏠 "+tb("BACK"): lambda u,c: u.message.reply_text("🏠 Main Menu", reply_markup=main_kb()),
    }
    h=BTN.get(txt)
    if h: await h(update, ctx)

# ══════════════════════════════════════════════
# BUTTON FUNCTIONS
# ══════════════════════════════════════════════
async def btn_upload(u,c):
    uid=u.effective_user.id
    mx=fmt_bytes(MAX_SIZE_PREMIUM if (is_owner(uid) or is_premium(uid)) else MAX_SIZE_FREE)
    await u.message.reply_text(
        f"📁 {tb('SEND YOUR FILE')}\n\n"
        f"✅ {tb('Supported:')} .py .js .ts .sh .rb .go .php\n"
        f"📦 {tb('Archives:')} .zip .tar .gz (auto-extracted!)\n"
        f"📝 {tb('Others:')} .html .ipynb .txt .json .md\n\n"
        f"📏 {tb('Max size:')} {mx}\n"
        f"⭐ {tb('Premium:')} {fmt_bytes(MAX_SIZE_PREMIUM)} limit"
    )

async def btn_files(u,c):
    uid=u.effective_user.id
    files=get_files(uid)
    if not files:
        await u.message.reply_text(f"📭 {tb('NO FILES')}\nUpload a file to get started!"); return
    kb=[]
    for f in files[:20]:
        fp=f['main_file'] or f['fpath']
        k=pkey(uid,Path(fp).name)
        alive=k in running_procs and running_procs[k].alive()
        st="🟢" if alive else "🔴"
        kb.append([InlineKeyboardButton(f"{st} {file_icon(f['fname'])} {f['fname'][:28]}", callback_data=f"file_{f['id']}")])
    await u.message.reply_text(f"🗂 {tb('YOUR FILES')} ({len(files)})", reply_markup=InlineKeyboardMarkup(kb))

async def btn_terminal(u,c):
    uid=u.effective_user.id
    term=Terminal(uid,u.effective_chat.id,c.bot,get_user_dir(uid))
    terminals[uid]=term
    msg=await u.message.reply_text(term.display(),reply_markup=term.kb())
    term.msg_id=msg.message_id

async def btn_ar(u,c):
    uid=u.effective_user.id
    r=get_user(uid); cur=bool(r['auto_restart']) if r else False
    db_run("UPDATE users SET auto_restart=? WHERE uid=?", (0 if cur else 1, uid))
    await u.message.reply_text(f"🔄 {tb('AUTO RESTART')}: {'🟢 ON' if not cur else '🔴 OFF'}")

async def btn_pkg(u,c):
    uid=u.effective_user.id
    await u.message.reply_text(f"📦 Send package name:\nExample: requests, flask, telethon")
    states[uid]={'pkg':True}

async def btn_pkgs(u,c):
    uid=u.effective_user.id
    pkgs=db_run("SELECT pkg FROM packages WHERE uid=?", (uid,), fetch='all') or []
    if not pkgs:
        await u.message.reply_text(f"📦 {tb('NO PACKAGES INSTALLED')}"); return
    pl="\n│  • ".join(p['pkg'] for p in pkgs[:30])
    await u.message.reply_text(f"╭──〔 📦 {tb('MY PACKAGES')} 〕──╮\n│\n│  • {pl}\n│\n╰──────────────────────────╯")

async def btn_status(u,c):
    uid=u.effective_user.id
    st=psutil.virtual_memory(); disk=psutil.disk_usage('/'); cpu=psutil.cpu_percent(0.5)
    procs=[k for k in running_procs if k.startswith(f"{uid}::") and running_procs[k].alive()]
    up=fmt_time(time.time()-float(get_setting('start_time') or time.time()))
    r=get_user(uid)

    gpu_t=""
    if GPU_AVAILABLE:
        try:
            g=GPUtil.getGPUs()[0]
            gpu_t=f"│  🎮 {tb('GPU:')} {g.load*100:.1f}%\n│  {pbar(g.load*100,100)}\n│\n"
        except: pass

    await u.message.reply_text(f"""╭────〔 📊 {tb("VPS STATUS")} 〕────╮
│
│  💻 {tb("CPU:")} {cpu:.1f}%
│  {pbar(cpu,100)}
│
│  🧠 {tb("RAM:")} {st.percent:.1f}%
│  {pbar(st.percent,100)}
│  {fmt_bytes(st.used)} / {fmt_bytes(st.total)}
│
│  💾 {tb("DISK:")} {disk.percent:.1f}%
│  {pbar(disk.percent,100)}
│
{gpu_t}│  ⚡ {tb("Your Processes:")} {len(procs)}/{MAX_PROC_PREMIUM if is_premium(uid) else MAX_PROC_FREE}
│  ⏱️ {tb("Uptime:")} {up}
│  🔄 {tb("Auto Restart:")} {'ON' if r and r['auto_restart'] else 'OFF'}
│  💰 {tb("Credits:")} {get_credits(uid) if not is_owner(uid) else '♾️'}
│
╰──────────────────────────────────╯""")

async def btn_ping(u,c):
    t=time.time(); msg=await u.message.reply_text("🏓")
    await msg.edit_text(f"🏓 {tb('PONG!')} {round((time.time()-t)*1000,1)}ms")

async def btn_console(u,c):
    uid=u.effective_user.id
    if not is_owner(uid): await u.message.reply_text(f"❌ {tb('OWNER ONLY!')}"); return
    total=db_run("SELECT COUNT(*) as c FROM users",fetch='one')['c']
    banned=db_run("SELECT COUNT(*) as c FROM users WHERE banned=1",fetch='one')['c']
    prem=db_run("SELECT COUNT(*) as c FROM users WHERE is_premium=1",fetch='one')['c']
    tc=db_run("SELECT SUM(credits) as s FROM users",fetch='one')['s'] or 0
    tf=db_run("SELECT COUNT(*) as c FROM files",fetch='one')['c']
    tr=db_run("SELECT SUM(run_count) as s FROM files",fetch='one')['s'] or 0

    await u.message.reply_text(f"""╭────〔 🖥 {tb("CONSOLE")} 〕────╮
│
│  👥 {tb("Total Users:")} {total}
│  🚫 {tb("Banned:")} {banned}
│  ⭐ {tb("Premium:")} {prem}
│  ⚡ {tb("Running:")} {len(running_procs)}
│  🖥 {tb("Terminals:")} {len(terminals)}
│  💰 {tb("Total Credits:")} {tc}
│  📁 {tb("Total Files:")} {tf}
│  🔢 {tb("Total Runs:")} {tr}
│
╰──────────────────────────────────╯""")

async def btn_account(u,c):
    uid=u.effective_user.id; uu=u.effective_user
    r=get_user(uid)
    if is_owner(uid): cr,st,exp="♾️","👑 Owner","Never"
    else:
        cr=str(r['credits'] if r else 0)
        st="⭐ Premium" if is_premium(uid) else "🆓 Free"
        exp=(r['premium_expiry'] or 'N/A')[:10] if r else 'N/A'
    rc=r['ref_code'] if r else 'N/A'; refs=r['total_refs'] if r else 0
    joined=(r['first_seen'] or 'N/A')[:10] if r else 'N/A'
    runs=r['total_runs'] if r else 0
    procs=[k for k in running_procs if k.startswith(f"{uid}::") and running_procs[k].alive()]

    await u.message.reply_text(f"""╭────〔 👤 {tb("MY ACCOUNT")} 〕────╮
│
│  🆔 {tb("ID:")} {mn(str(uid))}
│  👤 {tb("Name:")} {uu.first_name}
│  📛 {tb("Username:")} @{uu.username or 'N/A'}
│
│  💰 {tb("Credits:")} {cr}
│  👑 {tb("Status:")} {st}
│  📅 {tb("Expiry:")} {exp}
│
│  ⚡ {tb("Running:")} {len(procs)}
│  🔢 {tb("Total Runs:")} {runs}
│  👥 {tb("Referrals:")} {refs}
│  🔗 {tb("Ref Code:")} {mn(rc)}
│  📆 {tb("Joined:")} {joined}
│
╰──────────────────────────────────╯""", parse_mode=ParseMode.MARKDOWN)

async def btn_premium(u,c):
    uid=u.effective_user.id; r=get_user(uid)
    st="⭐ Active" if is_premium(uid) else "🆓 Free"
    exp=(r['premium_expiry'] or 'N/A')[:10] if r else 'N/A'
    kb=[[InlineKeyboardButton("📩 Buy Premium",url=f"https://t.me/{SUPPORT_USER}")]]
    await u.message.reply_text(f"""╭────〔 💎 {tb("PREMIUM")} 〕────╮
│
│  👑 {tb("Status:")} {st}
│  📅 {tb("Expiry:")} {exp}
│
│  ✅ {tb("Benefits:")}
│  • 500MB file size
│  • {MAX_PROC_PREMIUM} simultaneous processes
│  • No credit deduction
│  • Priority support
│  • Unlimited runtime
│
╰──────────────────────────────────╯""", reply_markup=InlineKeyboardMarkup(kb))

async def btn_credits(u,c):
    uid=u.effective_user.id
    cr=get_credits(uid) if not is_owner(uid) else "♾️"
    kb=[[InlineKeyboardButton("📩 Buy Credits",url=f"https://t.me/{SUPPORT_USER}")]]
    await u.message.reply_text(f"""╭────〔 💰 {tb("CREDITS")} 〕────╮
│
│  💰 {tb("Your Credits:")} {cr}
│  ⏱️ 1 Credit = 20 Minutes
│
│  🎁 {tb("Free Credits:")}
│  • 3 Credits on signup
│  • +5 per referral
│
│  💎 {tb("Buy Credits:")}
│  Contact owner below!
│
╰──────────────────────────────────╯""", reply_markup=InlineKeyboardMarkup(kb))

async def btn_ref(u,c):
    uid=u.effective_user.id; r=get_user(uid)
    if not r: await u.message.reply_text("❌ /start first"); return
    bi=await c.bot.get_me()
    link=f"https://t.me/{bi.username}?start={r['ref_code']}"
    await u.message.reply_text(
        f"🔗 {tb('REFERRAL')}\n\n"
        f"Your link:\n{mn(link)}\n\n"
        f"👥 Total referrals: {r['total_refs']}\n"
        f"💰 Earn 5 credits per referral!\n"
        f"📤 Share with friends!",
        parse_mode=ParseMode.MARKDOWN)

async def btn_admin(u,c):
    uid=u.effective_user.id
    if not is_owner(uid): await u.message.reply_text(f"❌ {tb('OWNER ONLY!')}"); return
    await u.message.reply_text(f"⚙️ {tb('ADMIN PANEL')}", reply_markup=admin_kb())

async def btn_guide(u,c):
    await u.message.reply_text(f"""╭────〔 📖 {tb("GUIDE")} 〕────╮
│
│  📁 {tb("Upload")} → Send any file
│  🗂 {tb("My Files")} → Manage & run
│  📦 {tb("ZIP")} → Auto-extracted!
│  ⚡ {tb("Terminal")} → Live terminal
│  🔄 {tb("Auto Restart")} → On crash
│  📦 {tb("Install Pkg")} → pip install
│
│  💰 {tb("Credits:")}
│  • 3 free on signup
│  • 1 credit = 20 min
│  • Refer = +5 credits
│
│  ⚡ {tb("Multiple Processes:")}
│  • Free: {MAX_PROC_FREE} at once
│  • Premium: {MAX_PROC_PREMIUM} at once
│
│  📦 {tb("ZIP Support:")}
│  • Upload ZIP → auto extract
│  • Browse files inside
│  • Select main file to run
│  • All files run together!
│
╰──────────────────────────────────╯""")

async def btn_all_users(u,c):
    if not is_owner(u.effective_user.id): return
    users=db_run("SELECT uid,fname,credits,is_premium FROM users ORDER BY uid DESC LIMIT 30",fetch='all') or []
    if not users: await u.message.reply_text("No users"); return
    lines=[f"• {uu['fname']} — {mn(str(uu['uid']))} — 💰{uu['credits']} {'⭐' if uu['is_premium'] else ''}" for uu in users]
    await u.message.reply_text(f"👥 {tb('ALL USERS')} ({len(users)}):\n\n"+"│ ".join(lines), parse_mode=ParseMode.MARKDOWN)

async def btn_stats(u,c):
    if not is_owner(u.effective_user.id): return
    total=db_run("SELECT COUNT(*) as c FROM users",fetch='one')['c']
    today=datetime.now().strftime('%Y-%m-%d')
    new=db_run("SELECT COUNT(*) as c FROM users WHERE first_seen LIKE ?",(f"{today}%",),fetch='one')['c']
    tr=db_run("SELECT SUM(run_count) as s FROM files",fetch='one')['s'] or 0
    await u.message.reply_text(f"""📊 {tb('BOT STATISTICS')}

👥 Total Users: {total}
📅 New Today: {new}
⚡ Active Processes: {len(running_procs)}
🖥 Active Terminals: {len(terminals)}
🔢 Total Script Runs: {tr}
🔧 Maintenance: {'ON' if maintenance() else 'OFF'}
📦 Bot Version: {get_setting('version') or '2.0'}""")

async def btn_prem_list(u,c):
    if not is_owner(u.effective_user.id): return
    users=db_run("SELECT uid,fname,premium_expiry FROM users WHERE is_premium=1",fetch='all') or []
    if not users: await u.message.reply_text("No premium users"); return
    lines=[f"• {uu['fname']} — {mn(str(uu['uid']))} — {(uu['premium_expiry'] or '')[:10]}" for uu in users]
    await u.message.reply_text("⭐ Premium:\n"+"│ ".join(lines), parse_mode=ParseMode.MARKDOWN)

async def btn_exp_list(u,c):
    if not is_owner(u.effective_user.id): return
    users=db_run("SELECT uid,fname,premium_expiry FROM users WHERE is_premium=0 AND premium_expiry IS NOT NULL",fetch='all') or []
    if not users: await u.message.reply_text("✅ No expired"); return
    lines=[f"• {uu['fname']} — {mn(str(uu['uid']))} — {(uu['premium_expiry'] or '')[:10]}" for uu in users]
    await u.message.reply_text("⌛ Expired:\n"+"│ ".join(lines), parse_mode=ParseMode.MARKDOWN)

async def btn_maintenance(u,c):
    if not is_owner(u.effective_user.id): return
    cur=maintenance(); set_setting('maintenance','0' if cur else '1')
    await u.message.reply_text(f"🔧 Maintenance: {'🔴 OFF' if cur else '🟢 ON'}")

async def btn_kill_all(u,c):
    if not is_owner(u.effective_user.id): return
    count=0
    for k,m in list(running_procs.items()):
        m.stop(); del running_procs[k]; count+=1
    await u.message.reply_text(f"💣 Killed {count} processes!")

# ══════════════════════════════════════════════
# VERCEL — REGISTER HANDLERS
# (Webhook mode: no polling, no health server)
# ══════════════════════════════════════════════
def register_handlers(app):
    """Register all Telegram handlers onto the given Application instance."""
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_handler(CallbackQueryHandler(handle_cb))
    logger.info("✅ Handlers registered (webhook mode)")
