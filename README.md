# Gym PR Tracker

A Django web app for tracking gym workouts, exercises, and personal records. Deployed on Railway with PostgreSQL and S3-compatible object storage.

## Features

### Workout Logging
- AJAX-based set entry — saves instantly, no page reloads
- Quick entry format: `SETSxREPSxWEIGHT` (e.g., `3x10x60` = 3 sets of 10 reps at 60kg)
- Struggle reps: `1x15+5+3x20` → effective reps = 15 + ceil((5+3)/2) = 19
- Compact and detail views for saved sets
- Create new exercises inline while logging

### Personal Records (3 Types)
- **Weight PR** — heaviest weight for a given rep count
- **Rep PR** — most reps at a given weight
- **Set PR** — most sets of the same reps+weight in one workout
- Auto-detected on every set save via full chronological recalculation
- Gold toast notifications on new PRs with "beat X from Y" context
- Manual PR entry and manual PR toggle (🏆) on individual sets
- PR list page with exercise and type filters

### Dashboard
- Monthly calendar with color-coded days (green = workout, gold = PR, gradient = both, blue outline = today)
- Month/year picker popup for quick navigation
- Exercise filter with compact/detail toggle
- PR filter to show PRs for the displayed month
- Recent workouts list

### Exercise Management
- 20 default exercises seeded on deploy
- Custom exercise creation (per-user, with uniqueness constraint)
- Searchable, sortable exercise list with Standard/Custom badges
- Detail view with media gallery
- Edit/delete with permission logic (own exercises or superuser)

### Media
- Multiple images and videos per exercise and per workout
- Upload/delete is superuser-only
- Supported: jpg, jpeg, png, gif, webp, mp4, mov, webm, avi
- Files stored in Railway S3 Bucket, served via backend proxy
- Auto-cleanup: files deleted from bucket when records are deleted (via `post_delete` signals)

### Mobile
- Responsive layout (max-width 800px container)
- Hamburger menu at ≤600px
- Calendar font scaling at ≤380px

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django 6.0.2 |
| Python | 3.14.3 |
| Database (prod) | PostgreSQL via Railway |
| Database (dev) | SQLite |
| Object Storage | Railway Bucket (S3-compatible) |
| Static Files | WhiteNoise |
| WSGI Server | Gunicorn |
| S3 Client | django-storages + boto3 |
| Image Processing | Pillow |

## Project Structure

```
gym_tracker/
├── manage.py
├── Procfile
├── requirements.txt
├── runtime.txt
├── mysite/                    # Django config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/                  # Auth app (login/logout)
├── workouts/                  # Core app
│   ├── models.py              # Exercise, Workout, WorkoutSet, PersonalRecord, ExerciseMedia, WorkoutMedia
│   ├── views.py               # All views + AJAX API endpoints
│   ├── services.py            # PR recalculation logic
│   ├── forms.py               # ExerciseForm, ManualPRForm, parse_sets()
│   ├── urls.py                # All URL routes
│   ├── management/commands/   # load_default_exercises, create_admin
│   └── templates/workouts/    # All templates
└── templates/
    └── base.html              # Global layout, nav, hamburger menu
```

## API Endpoints

All require authentication. POST only.

| Endpoint | Purpose |
|----------|---------|
| `/api/add-sets/` | Save sets (AJAX), triggers PR recalculation |
| `/api/delete-set/` | Delete a set, recalculates PRs, auto-deletes empty workouts |
| `/api/toggle-pr/` | Manually mark/unmark a set as PR |
| `/api/create-exercise/` | Create exercise inline from workout page |
| `/api/upload-media/` | Upload images/videos (superuser only) |
| `/api/delete-media/` | Delete media files (superuser only) |

## Local Development

```bash
# Clone
git clone https://github.com/Martin-Doynov/Gym-PR-Tracker-app.git
cd gym_tracker

# Virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Seed default exercises
python manage.py load_default_exercises

# Create superuser
python manage.py createsuperuser

# Run dev server
python manage.py runserver
```

No environment variables needed locally — defaults to SQLite and filesystem storage.

## Deployment (Railway)

### Services
- **Web service** — Django app via Gunicorn
- **PostgreSQL** — Managed database
- **Bucket** — S3-compatible object storage for media

### Environment Variables (on web service)

| Variable | Value |
|----------|-------|
| `SECRET_KEY` | Random secret |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | Your Railway domain |
| `CSRF_TRUSTED_ORIGINS` | `https://your-domain.railway.app` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `AWS_STORAGE_BUCKET_NAME` | `${{BucketName.BUCKET}}` |
| `AWS_S3_ENDPOINT_URL` | `${{BucketName.ENDPOINT}}` |
| `AWS_ACCESS_KEY_ID` | `${{BucketName.ACCESS_KEY_ID}}` |
| `AWS_SECRET_ACCESS_KEY` | `${{BucketName.SECRET_ACCESS_KEY}}` |
| `AWS_S3_REGION_NAME` | `${{BucketName.REGION}}` |

Replace `BucketName` with your bucket's actual name on the Railway canvas.

### Procfile

```
web: python manage.py collectstatic --noinput && python manage.py migrate && python manage.py load_default_exercises && gunicorn mysite.wsgi
```

Runs on every deploy: static files collected, migrations applied, default exercises seeded (idempotent), then Gunicorn starts.

## Architecture Decisions

- **Services layer** (`services.py`) — PR recalculation is isolated from views. Wipes and rebuilds all auto PRs chronologically per user+exercise. Manual PRs are untouched.
- **Lazy workout creation** — Visiting a date doesn't create a Workout record. Only saving a set does (`get_or_create`). Prevents empty workout clutter.
- **Empty workout cleanup** — Deleting all sets from a workout auto-deletes the workout. Dashboard/history queries use `Count('sets')` annotation as a safety net.
- **Media proxy** — Railway Buckets are private. `serve_media` view reads from S3 and streams to the client. No public bucket URLs exposed.
- **`post_delete` signals** — Deleting media records auto-deletes the file from S3. Covers cascade deletes (e.g., deleting an exercise removes its media files).