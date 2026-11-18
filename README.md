# NITC Reporting

Flask and SQLite prototype for coordinating physical admission reporting at NIT Calicut. Students book a reporting token and check their place in the queue. Staff use separate views for intake and verification.

[Quick start](#quick-start) · [Project layout](#project-layout)

## Quick start

Run locally with Python 3 and use test records.

```bash
cd NITC-Physical-Reporting/queue-system
python3 -m venv .venv
source .venv/bin/activate
python -m pip install Flask Flask-SQLAlchemy
python app.py
```

Open [localhost:5000](http://localhost:5000).

## Project layout

| Path | Purpose |
| --- | --- |
| [`queue-system/app.py`](NITC-Physical-Reporting/queue-system/app.py) | Application routes, queue state, and persistence |
| [`queue-system/templates/`](NITC-Physical-Reporting/queue-system/templates/) | Student, queue status, and staff screens |
| [`queue-system/static/`](NITC-Physical-Reporting/queue-system/static/) | Browser-side interactions |
