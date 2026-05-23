# Setup Guide

This guide walks you through running TaskFlow locally and deploying it. It assumes you have a Firebase project and (optionally) Gemini and Azure Face accounts.

## 1. Prerequisites

- **Python 3.10+** and `pip`
- A **Firebase** project with **Firestore** enabled
- (Optional) **Google Gemini** API key — only needed for receipt scanning
- (Optional) **Azure Face API** resource — only needed for facial-recognition attendance

## 2. Clone and install

```bash
git clone https://github.com/tech-zencia/zencia-taskflow.git
cd zencia-taskflow

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

## 3. Create your environment file

```bash
cp .env.example .env
```

Then fill in the values as described below.

### 3a. Flask

| Variable | How to get it |
| --- | --- |
| `SECRET_KEY` | Run `python -c "import secrets; print(secrets.token_hex(32))"` and paste the output. |
| `FLASK_ENV` | `development` locally, `production` when deployed. |
| `SUPER_ADMIN_EMAIL` | Email of an existing registered user to promote to super-admin on startup. |

### 3b. Firebase Web config

1. Go to **Firebase Console → Project Settings → General**.
2. Under **Your apps**, select (or create) a **Web app**.
3. Copy the config values into:
   `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID`,
   `FIREBASE_STORAGE_BUCKET`, `FIREBASE_MESSAGING_SENDER_ID`,
   `FIREBASE_APP_ID`, `FIREBASE_MEASUREMENT_ID`.

### 3c. Firebase Admin SDK (Service Account)

1. **Firebase Console → Project Settings → Service Accounts**.
2. Click **Generate new private key** — this downloads a JSON file. **Keep it secret.**
3. Open the JSON and copy each field into the matching `FIREBASE_*` variable in `.env`:
   - `private_key_id` → `FIREBASE_PRIVATE_KEY_ID`
   - `private_key` → `FIREBASE_PRIVATE_KEY` (keep it one line, wrapped in double quotes, with the `\n` sequences intact)
   - `client_email` → `FIREBASE_CLIENT_EMAIL`
   - `client_id` → `FIREBASE_CLIENT_ID`
   - the URL fields map directly to their `FIREBASE_*` counterparts.

> The app reads these in `firebase_config.py` to initialize `firebase-admin`. If the private key is malformed (missing `\n`), Firebase init will fail.

### 3d. Gemini (optional — receipt scanning)

1. Go to **Google AI Studio → API keys**, create a key.
2. Set `GEMINI_API_KEY`.

### 3e. Azure Face API (optional — attendance)

1. In the **Azure Portal**, create a **Face** resource.
2. From **Keys and Endpoint**, copy a key into `AZURE_FACE_API_KEY` and the endpoint into `AZURE_FACE_ENDPOINT`.

### 3f. Cron (optional)

`CRON_SECRET` protects the `/api/cron/auto-checkout` endpoint. Set any random string; callers must send `Authorization: Bearer <CRON_SECRET>`.

## 4. Run locally

```bash
python app.py
```

Open <http://localhost:5083>. Register a user, then make sure that user's email matches `SUPER_ADMIN_EMAIL` to get admin access on the next restart.

## 5. Deploy (Vercel)

The repo includes `vercel.json`. To deploy:

1. Install the Vercel CLI (`npm i -g vercel`) or connect the repo in the Vercel dashboard.
2. Add **every variable from `.env`** under **Project → Settings → Environment Variables** (do not commit `.env`).
3. Deploy. The included cron config calls `/api/cron/auto-checkout` daily; ensure `CRON_SECRET` is set so the endpoint is protected.

## 6. Troubleshooting

- **Firebase init error / bad private key** — confirm `FIREBASE_PRIVATE_KEY` is in double quotes and its newlines are written as literal `\n`.
- **`load_dotenv` not loading values** — make sure the file is named exactly `.env` in the project root.
- **Admin pages 403/redirect** — confirm your user is promoted: the email must equal `SUPER_ADMIN_EMAIL`, then restart the app.
