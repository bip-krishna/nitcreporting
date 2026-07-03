# NITC Reporting

Flask-based queue management system for physical document reporting at NIT Calicut.

## Features

- **Student Portal** — Register, login, book slots, upload required documents (Class 10/12 marksheets, category certificate, fee receipt)
- **Admin Dashboard** — Two-tier verification workflow, token queue management, Chanakya portal integration
- **Token System** — Auto-generated tokens with time slots, fee status tracking, and real-time queue position

## Tech Stack

- **Backend:** Flask (Python)
- **Database:** SQLite via Flask-SQLAlchemy
- **Auth:** Session-based with role separation (student vs admin)
- **Frontend:** Jinja2 templates, HTML/CSS

## Setup

```bash
git clone https://github.com/bip-krishna/nitcreporting.git
cd nitcreporting/NITC-Physical-Reporting/queue-system
pip install flask flask-sqlalchemy
python app.py
```

Open `http://localhost:5000` to access the application.
