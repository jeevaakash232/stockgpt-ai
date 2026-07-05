# 🚀 StockGPT AI — Deployment Guide
## Render (Backend) + Netlify (Frontend) — Both Free

---

## STEP 1 — Push code to GitHub

### 1a. Create a GitHub account
Go to https://github.com and sign up (free).

### 1b. Create a new repository
- Click **+** → **New repository**
- Name: `stockgpt-ai`
- Set to **Public**
- Do NOT add README (your code already has one)
- Click **Create repository**

### 1c. Push your code

Open a terminal in `D:\StockGPT` and run:

```bash
git init
git add .
git commit -m "StockGPT AI v2.0 - Initial deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/stockgpt-ai.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

---

## STEP 2 — Deploy Backend on Render

### 2a. Sign up at render.com
Go to https://render.com → Sign up with GitHub (easiest).

### 2b. Create a new Web Service
- Click **New +** → **Web Service**
- Connect your GitHub account → select `stockgpt-ai` repo
- Fill in these settings:

| Setting | Value |
|---------|-------|
| **Name** | `stockgpt-api` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements_stockgpt.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | Free |

### 2c. Add Environment Variables
Click **Environment** tab → Add these one by one:

| Key | Value |
|-----|-------|
| `GROQ_API_KEY` | `gsk_RmwdW2...` (your real key) |
| `MODEL_NAME` | `meta-llama/llama-4-scout-17b-16e-instruct` |
| `ANGEL_API_KEY` | `z0ikbKgb` |
| `ANGEL_CLIENT_ID` | `AAAF142252` |
| `ANGEL_PASSWORD` | `6380` |
| `ANGEL_TOTP_SECRET` | `6YGMBDZ5TUUY3RGDJQQAUISJBQ` |
| `FRONTEND_URL` | *(leave blank for now — fill after Netlify deploy)* |

### 2d. Deploy
Click **Create Web Service** → wait 3-5 minutes for build.

### 2e. Copy your backend URL
After deploy, Render shows your URL at the top:
```
https://stockgpt-api.onrender.com
```
**Copy this URL — you need it in Step 3.**

---

## STEP 3 — Update frontend with your Render URL

Open `frontend/js/api.js` and change line 10:

```javascript
// Change this placeholder:
const RENDER_BACKEND_URL = "https://stockgpt-api.onrender.com";

// To your ACTUAL Render URL (copy from Step 2e):
const RENDER_BACKEND_URL = "https://YOUR-ACTUAL-NAME.onrender.com";
```

Save the file, then commit and push:

```bash
git add frontend/js/api.js
git commit -m "Set Render backend URL"
git push
```

---

## STEP 4 — Deploy Frontend on Netlify

### 4a. Sign up at netlify.com
Go to https://netlify.com → Sign up with GitHub.

### 4b. Create a new site
- Click **Add new site** → **Import an existing project**
- Connect GitHub → select `stockgpt-ai`
- Fill in:

| Setting | Value |
|---------|-------|
| **Base directory** | `frontend` |
| **Publish directory** | `frontend` |
| **Build command** | *(leave completely empty)* |

- Click **Deploy site**

### 4c. Copy your Netlify URL
Netlify gives you a URL like:
```
https://stockgpt-abcd1234.netlify.app
```
**Copy this URL.**

---

## STEP 5 — Set FRONTEND_URL on Render

Go back to Render → your service → **Environment** tab:
- Find `FRONTEND_URL`
- Set value to your Netlify URL: `https://stockgpt-abcd1234.netlify.app`
- Click **Save Changes** → Render auto-redeploys

---

## STEP 6 — Verify it works

1. Open your Netlify URL in a browser
2. The dashboard should load with live data
3. Open browser DevTools (F12) → Console
   - Should show: `StockGPT AI v2.0 ready.`
   - Should NOT show any red CORS errors

Test the backend directly:
```
https://YOUR-NAME.onrender.com/docs
```
This shows the interactive API documentation.

---

## Important Notes

### Free tier limits
| Platform | Limit |
|----------|-------|
| Render free | Sleeps after 15 min of no traffic. First request takes ~30 seconds to wake up. |
| Netlify free | 100GB bandwidth/month (more than enough) |

### To give it a custom domain (optional)
- Buy a domain on [Namecheap](https://namecheap.com) (~₹800/year for .com)
- In Netlify: **Domain settings** → **Add custom domain**

### Angel One session
Your TOTP auto-renews — no manual intervention needed.
The session refreshes automatically every 23 hours.

### Keep secrets safe
- The `.env` file is in `.gitignore` — it will NOT be pushed to GitHub
- All secrets are stored as Render environment variables only

---

## Quick Reference URLs (fill in after deploy)

| Service | URL |
|---------|-----|
| Backend API | `https://____________.onrender.com` |
| API Docs | `https://____________.onrender.com/docs` |
| Frontend | `https://____________.netlify.app` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Site loads but data shows `—` | Backend is sleeping — wait 30s and refresh |
| CORS error in console | Check `FRONTEND_URL` is set correctly in Render env vars |
| `401 Invalid API Key` | Check `GROQ_API_KEY` in Render environment variables |
| Build failed on Render | Check that `backend/requirements_stockgpt.txt` exists |
| Excel download fails | Normal on free Render — memory-intensive, may timeout |
