# 🌺 Ultra VPS Hosting Bot — Vercel Edition

Multi-process Telegram bot, Vercel Serverless-এ Webhook মোডে চলে।

---

## ⚠️ গুরুত্বপূর্ণ নোট

Vercel **Serverless** platform। এখানে long-running process (polling) চলে না।
তাই বটটি **Webhook** মোডে রূপান্তর করা হয়েছে —
Telegram নিজেই প্রতিটি message Vercel-এর URL-এ পাঠাবে।

> **সীমাবদ্ধতা:** Vercel-এ Terminal ও Process Monitor ফিচার সম্পূর্ণ কাজ নাও করতে পারে  
> কারণ Vercel প্রতিটি request-এর পর environment মুছে ফেলে।  
> File upload, user management, credits — সব কাজ করবে।

---

## 📁 ফাইল স্ট্রাকচার

```
vps-bot/
├── api/
│   └── webhook.py        ← Vercel serverless entry point
├── bot_core.py           ← সমস্ত bot logic (handlers)
├── vercel.json           ← Vercel configuration
├── requirements.txt      ← Python dependencies
├── setup_webhook.py      ← Webhook register script (একবার চালাও)
├── .env.example          ← Environment variable template
└── .gitignore
```

---

## 🚀 Step-by-Step Deploy গাইড

### Step 1 — GitHub-এ Code তোলো

```bash
git init
git add .
git commit -m "Ultra VPS Bot - Vercel"
git branch -M main
git remote add origin https://github.com/তোমার-username/vps-bot.git
git push -u origin main
```

### Step 2 — Vercel-এ Project তৈরি করো

1. [vercel.com](https://vercel.com) → **Sign In** (GitHub দিয়ে)
2. **"Add New Project"** → তোমার GitHub repo সিলেক্ট করো
3. Framework: **Other** (Python)
4. **Deploy** বাটনে ক্লিক করো

### Step 3 — Environment Variables সেট করো

Vercel Dashboard → তোমার Project → **Settings → Environment Variables**

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | BotFather থেকে পাওয়া token |
| `OWNER_ID` | তোমার Telegram User ID |
| `SUPPORT_USERNAME` | তোমার username (@ ছাড়া) |

> সেট করার পর **Redeploy** করো!

### Step 4 — Webhook Register করো

Deploy সফল হলে তোমার URL পাবে, যেমন: `https://vps-bot-xyz.vercel.app`

তারপর নিচের command চালাও (terminal বা cmd-এ):

```bash
# Windows
set BOT_TOKEN=তোমার_token
set VERCEL_URL=https://vps-bot-xyz.vercel.app
python setup_webhook.py

# Mac/Linux
BOT_TOKEN=তোমার_token VERCEL_URL=https://vps-bot-xyz.vercel.app python setup_webhook.py
```

অথবা interactively:
```bash
python setup_webhook.py
# এরপর token ও URL দিতে বলবে
```

### Step 5 — Test করো

Telegram-এ তোমার বটে `/start` পাঠাও। ✅

---

## 🔄 Update করতে হলে

```bash
git add .
git commit -m "update"
git push
```

Vercel automatically redeploy করবে।

---

## 🛠 Troubleshooting

| সমস্যা | সমাধান |
|--------|--------|
| বট reply করছে না | Vercel logs চেক করো: Dashboard → Functions → Logs |
| "BOT_TOKEN not set" | Environment Variables ঠিকমতো সেট করো ও Redeploy করো |
| Webhook error | `setup_webhook.py` আবার চালাও |
| Database error | Vercel-এ `/tmp` ছাড়া persistent storage নেই — সমস্যা হলে বলো |

---

## 📞 Support

[@Hridoy6t669](https://t.me/Hridoy6t669)
