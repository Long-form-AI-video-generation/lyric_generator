# LyricVid

LyricVid is an internal browser tool for creating synced lyric videos from an MP3 or WAV file. The refactored system follows the product specification in `requirememts.md`: a Next.js wizard for upload/edit/preview/export, a FastAPI backend for transient jobs, optional Celery + Redis workers, Whisper transcription, FFmpeg MP4 rendering, and no database-backed persistence.

## What Is Included

- `frontend/` - Next.js 14 App Router, TypeScript, Tailwind, Zustand, Framer Motion, Lucide icons.
- `backend/` - FastAPI API, Pydantic v2 schemas, upload validation by magic bytes, transient filesystem job storage, preset generation, Whisper boundary, ASS subtitle generation, FFmpeg rendering.
- `docker-compose.yml` - frontend, backend, Celery worker, and Redis.

## Local Development

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

By default `USE_CELERY=false`, so transcription and export jobs run as FastAPI background tasks for local development. For production-like async workers, set `USE_CELERY=true` and run Redis plus:

```bash
celery -A backend.tasks.celery_app.celery_app worker --loglevel=INFO
```

## Docker

```bash
docker compose up --build
```

The compose stack exposes:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Redis: internal service only

Whisper model weights are cached in the `whisper-cache` Docker volume. For a GPU server, set `WHISPER_DEVICE=cuda` and use an appropriate CUDA-enabled Python base image for `backend/Dockerfile`.

## Authentication & Database Setup

LyricVid includes a multi-tenant authentication and private beta invitation system backed by **PostgreSQL** (e.g. [Neon](https://neon.tech)).

### 1. Database Configuration

Add your PostgreSQL connection string to your `.env` file:

```env
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

Run database migrations using Alembic:

```bash
alembic upgrade head
```

### 2. Creating an Admin Account

Bootstrap the initial administrator account using the CLI script:

```bash
python scripts/create_admin.py --email admin@example.com --password YourSecurePassword --credits 100
```

Once logged in as an admin:
- Click the **`LV LyricVid`** logo in the top-left of the wizard header to open the **Workspace Menu**.
- Use the **"Invite Beta Tester"** section to invite new users and grant starting video generation credits.

### 3. Video Credits & Quota System

To prevent runaway GPU/CPU and LLM costs during beta testing, the platform enforces video generation quotas stored in the `user_quotas` table:

- **Credit Allocation**:
  - **Beta Testers**: Receive **3 credits** by default upon accepting their invitation (allows generating 3 complete videos). Admins can customize this amount (from 1 to 100 credits) when issuing the invite.
  - **Admins**: Granted **100 credits** by default when created via `scripts/create_admin.py` (customizable using the `--credits` flag).
- **Enforcement (`backend/core/permissions.py`)**:
  - Each video export (`POST /api/export`) checks that `credits_remaining > 0` before initiating rendering.
  - Each successful video export consumes 1 credit.
  - When balance reaches 0, further export requests return `HTTP 402 Payment Required` until an admin increases the allowance.
- **UI Integration**:
  - Real-time remaining balance is prominently displayed in the top header (`⚡ {credits} credits`) and inside the workspace sidebar.

---

## Email Setup for Beta Invites (SMTP)

Invitations are delivered automatically via HTML email containing single-use activation links.

### Option A: Using Gmail SMTP (Zero domain setup required)

To send invitations directly without owning a custom domain:

1. Enable **2-Step Verification** on your Google Account: [myaccount.google.com/security](https://myaccount.google.com/security)
2. Generate an **App Password**:
   - Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - App name: `LyricVid`
   - Copy the 16-character password provided (e.g. `zkig huhu hoho hoho`).
3. Add these variables to your `.env` file:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
EMAIL_FROM="LyricVid Beta <your_email@gmail.com>"
FRONTEND_BASE_URL=http://localhost:3000
```

### Option B: Using a Production SMTP Service (SendGrid, Mailgun, Amazon SES, Postmark)

When deploying to a live server with a custom domain, configure your provider's SMTP credentials:

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your_sendgrid_api_key
EMAIL_FROM="LyricVid Beta <invites@yourdomain.com>"
FRONTEND_BASE_URL=https://your-frontend-domain.com
```

### Important Deployment Notes for SMTP:
- **`FRONTEND_BASE_URL`**: Set this to the public URL of your frontend (e.g. `https://your-app.vercel.app` or `https://lyricvid.ai`). This ensures the activation links in emails direct users to the deployed app.
- **Local Fallback**: If SMTP credentials are not set in `.env`, the system safely falls back to logging the activation link to the backend console so you can still test invitations locally without an active email server.

---

## Cloud Object Storage Setup (Cloudflare R2 / S3)

To prevent data loss on server restarts and allow horizontal scaling across multiple container replicas, LyricVid supports **Cloudflare R2** (or any S3-compatible storage) for storing user audio uploads and rendered MP4 exports.

Cloudflare R2 is recommended because it provides **10 GB storage and 10 million operations free per month with $0 bandwidth/egress fees**.

### 1. Create a Bucket in Cloudflare
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com).
2. Go to **R2 Object Storage** in the left menu.
3. Click **Create bucket**, name it `lyricvid-media` (or your preferred name), and click **Create bucket**.

### 2. Generate an R2 API Token
1. Under **R2 Object Storage**, click **Manage R2 API Tokens** on the right side.
2. Click **Create API Token**.
3. Set permissions to **Object Read & Write**.
4. Choose your bucket (`lyricvid-media`) under **Apply to specific buckets only** (or select all buckets).
5. Click **Create API Token**.
6. Copy the **Access Key ID**, **Secret Access Key**, and **Endpoint URL** (formatted as `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`).

### 3. Add to Your `.env` File

```env
USE_S3_STORAGE=true
R2_BUCKET=lyricvid-media
R2_ENDPOINT_URL=https://<YOUR_CLOUDFLARE_ACCOUNT_ID>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_REGION=auto
S3_PRESIGNED_EXPIRY_SECONDS=3600
```

> **Local Fallback:** If `USE_S3_STORAGE=false` or credentials are left empty, the application automatically uses local disk storage (`/tmp/lyricvid`) for local offline development.

---

## API Summary

- `POST /api/auth/login` - authenticate user and return signed JWT token.
- `GET /api/auth/me` - get current user profile and credit balance.
- `GET /api/auth/invites/verify?token=...` - verify validity of an invite token.
- `POST /api/auth/invites/accept` - set account password and activate invite.
- `POST /api/admin/invites` - (Admin only) generate invitation and dispatch SMTP email.
- `GET /api/projects` - list all saved projects and drafts for authenticated user.
- `GET /api/projects/{id}` - get project details with lyrics and storyboard scenes.
- `PATCH /api/projects/{id}` - update project title, styling, and lyrics.
- `DELETE /api/projects/{id}` - soft delete project.
- `POST /api/upload` - upload MP3/WAV, returns a `job_token` and `project_id`.
- `POST /api/transcribe` - queue Whisper transcription for an uploaded job.
- `GET /api/status/{job_token}` - poll transcription/render progress.
- `GET /api/lyrics/{job_token}` - fetch generated lyrics JSON.
- `POST /api/export` - queue MP4 rendering with final lyrics and background.
- `GET /api/download/{job_token}` - stream the rendered MP4 or redirect to presigned R2 URL.
- `GET /api/presets` - list built-in background presets.

## Data Retention

User accounts, credit quotas, projects, lyrics, and storyboard scenes are securely persisted in PostgreSQL. Media files and render outputs are stored in Cloudflare R2 / S3 when configured, or temporarily under `LYRICVID_TEMP_ROOT` in local development mode.

## Verification

Lightweight tests avoid loading Whisper:

```bash
pytest backend/tests/
```

The Whisper path is intentionally isolated in `backend/services/whisper_service.py`; run that portion on a machine with enough CPU/GPU capacity and preloaded model weights.
