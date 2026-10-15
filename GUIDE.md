# Paralympic project — implementation guide

Due **16 Oct**. Everything below was run and tested on SQLite; **run it once on your PostgreSQL before you present** (steps in section 2).

---

## 1. Which part is for which system

| # | Requirement | What the user sees | Files (new = ★) | Owner (from your to-do sheet) |
|---|---|---|---|---|
| 1 | Register / login / logout for **admin, agent, sporter, judge, visitor** | `/login/`, `/register/` (role dropdown) | `pages/views.py` → `auth()`, `templates/auth.html`, `pages/models.py` → `Profile.role`, ★`pages/permissions.py` | **Pathomkant** |
| 1 | Guests can see results + total medals; **admin manages everything** | everything under `/`, `/events/`, `/athletes/`, `/results/` works without login; `/manage/` is staff only | ★`pages/public_views.py`, `pages/views.py` → `admin()` | **Pathomkant** |
| 2 | **EVENT page** = schedule of competition events | `/events/` (public, searchable, Download CSV); create/edit in `/manage/events/` | ★`pages/public_views.py` → `events_page`, ★`templates/events.html`, `templates/admin.html` | **Channiti** (public page), **Pathomkant** (management) |
| 3 | Manage athletes of each event; **judge optional** | `/manage/events/` → people icon (athletes) + "Judge (optional)" dropdown | `Event.judge`, `ParticipatingAthlete`, `templates/admin.html` | **Pathomkant** |
| 4 | **RESULT page**: admin / judge edit scores | `/results/` → open an event → edit forms appear only for admin or that event's judge | ★`public_views.py` → `results_page`, `result_detail`; ★`templates/results.html`, ★`templates/result_detail.html` | **Patipan** |
| 5 | **Medals calculated from results, or edited manually; final result in POINTS** | "Save scores & calculate" (auto) and "Save manual values" (manual) on the result page | `pages/scoring.py` → `calculate_event()`, ★`PointTable` model, ★`import_points` command | **Komchan** |
| 6 | **Total medal count = opening page** | `/` medal table (gold/silver/bronze/total/points per country) | ★`public_views.py` → `home_page_view`, `templates/home.html` | **Komchan** |
| — | Athlete page (searchable, from CSV) | `/athletes/`, `/athlete/id/<bib>/` | ★`athletes_page`, `templates/athletes.html`, ★`templates/athlete_detail.html`, ★`import_athletes` | **Channiti** |
| — | Database structure | models + migrations 0012, 0013 | `pages/models.py`, `pages/migrations/` | **Patipan** |

Shared: `templates/base_public.html` + `static/public.css` (look of all public pages).

### How the pieces connect (one sentence each)
- **Admin** creates the **Event** (`/manage/events/`), optionally picks a **Judge**, then adds **athletes** to it (`ParticipatingAthlete`).
- The **judge/admin** opens `/results/<event no.>/`, enters each athlete's attempts → `calculate_event()` turns every valid mark into **points** with the `PointTable` formula, **ranks by points**, gives medals to ranks 1–3, saves a `Result`.
- The **home page** just sums `Result.medal` per country, so it updates by itself.

---

## 2. Steps to implement

1. **Get the files in.** Unzip `paralympic-changes.zip` over your repo (same folder layout). Or: `git apply paralympic-changes.patch`. Then commit.
2. **Install + configure**
   ```bash
   pip install -r requirements.txt
   cp .env.example .env      # fill DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, MAPBOX_KEY, SECRET_KEY
   ```
3. **Create the database** (once): `CREATE DATABASE paralympic;` in psql / pgAdmin.
4. **Migrate**: `python manage.py migrate`  (adds roles, judge, point tables, and seeds Long Jump T61–T64 parameters).
5. **Load data**
   ```bash
   python manage.py import_athletes Athlests.member.csv
   python manage.py import_events data/events.sample.csv     # replace with your real schedule
   python manage.py createsuperuser                          # this is your ADMIN
   ```
6. **Run + test**: `python manage.py runserver`, then `python manage.py test` (21 tests).
7. **Demo script (5 min)**
   1. Logged out: show `/` medal table, `/events/`, `/athletes/`, `/results/`.
   2. Register a *judge* (`/register/`), log out.
   3. Log in as admin → `/manage/users/` (see roles) → `/manage/events/` → edit event 101, set the judge → click the people icon, add athletes.
   4. Log in as the judge → `/results/101/` → enter attempts → **Save scores & calculate** → ranks, points, medals appear.
   5. Show `/` again: medal table updated. Show manual edit on the result page.

---

## 3. Things you must fix / decide (honest list)

1. **Points parameters only exist for Long Jump T61–T64.** Your CSV has 30 different classes (T11…T54, F20…F57), but only 6 athletes are T62–T64. For any other event/class the calculator says *"No points-table row…"* — manual entry still works. **You need the official points table from your course/brief** (the ERD's FIELDPOINT/TRACKPOINT: gender, event, class, a, b, c). Put it in a CSV (`kind,event,classification,gender,a,b,c`) and run `python manage.py import_points data/points.csv`. I did **not** invent coefficients. Also check the track formula in the brief: the code uses `a·exp(−exp(b − c·seconds))` for track, which I could not verify.
2. **Duplicate athlete ID in your CSV:** ID `805` is used by both *Nathayod CHAIKHAN* and *Pichet KRUNGGET*. The importer loads the first and warns about the second. Give one a new ID in the CSV.
3. **The CSV has no events.** Athletes' events aren't in it, so the schedule (`data/events.sample.csv`) is a 2-row sample — fill in the real one.
4. **Judges self-register.** Anyone can pick "Judge", but a judge can only edit events an admin assigned to them, so the risk is small. If your brief wants approval, add an "approved" flag.
5. **Medal table order** is gold → silver → bronze, with total points shown. If your brief wants countries ordered by points, change `.order_by(...)` in `medal_table()`.
6. **Run on PostgreSQL.** I tested on SQLite; the migrations use standard Django operations so they should work, but I could not run Postgres here.
7. **Security:** the old `SECRET_KEY` was committed to a public repo. Settings now read it from `.env`; generate a new one and don't reuse the old one.
8. **`/manage/medal-calculator/`** (old Long Jump-only page) still works. The new result page does the same job for all events, so after your team agrees you can delete the old one.

### Bugs fixed in existing code
- `views.py`: `results: results` (variable used as dict key) → `'results'`.
- Edit athlete typo `dateOfbirth` → `dateOfBirth`; empty date no longer crashes add/edit.
- Athlete search `Q(country) & Q(first) | Q(last)` precedence bug (ignored country filter for last-name matches).
- Gender `"Men"/"Women"` (as in your CSV) was not recognised by the scoring code.
- Register silently redirected on errors → now shows the reason.
- `LOGIN_URL` was relative (`'login/'`) → `'/login/'`.
- Public athlete list no longer shows e-mails to non-admins.
