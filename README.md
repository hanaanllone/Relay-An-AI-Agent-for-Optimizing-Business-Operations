# Relay — Your Business, Optimized.

Relay is a proactive AI business-operations agent. It uses company-specific policies and business data to call employees, customers, and software owners through CALL-E, capture structured outcomes, and update the company's operational state.

## Stack

- React + Vite frontend
- Flask REST API
- SQLite database
- CALL-E for phone conversations
- Python `time` / `datetime` for current server time and operational timestamps

## Demo login

- Email: `admin@relaydemo.com`
- Password: `demo123`

## Features

### Company workspace
- Company sign-in
- Demo company workspace
- Company-specific policies
- Policy upload for UTF-8 `.txt` / `.md` files
- Editable policy text
- Settings to enable/disable major Relay capabilities

### Dashboard
- Employee attendance: present, absent, late, remote, on leave
- Employee attention flags
- Upcoming meetings
- Company memos
- Customer renewals and account health
- Software inventory
- Monthly software spend
- Potential unused software spend
- Recent operational calls and activity

### Employee Operations
Each employee has:
- Present / absent / late / remote / on leave status
- Offboarding status
- Department
- Role
- Assigned software
- Upcoming meetings
- Phone number

Relay can call an employee to determine whether they are:
- On leave
- Working remotely
- Running late
- Forgot to check in
- Facing a problem requiring escalation

The structured result is written to SQLite and appears in the call log.

Offboarding can also reclaim an associated software seat, creating a cross-pillar workflow.

### Customer Lifecycle
Each customer has:
- Current plan
- Renewal date
- Customer status
- Recent issue
- Usage
- Contact number

Actions:
- Renewal call
- Plan information
- Issue follow-up
- Feedback call

### Software / Vendor Lifecycle
For each SaaS tool Relay tracks:
- Department
- Owner
- Purchased seats
- Active seats
- Utilization
- Cost per seat
- Monthly spend
- Renewal date
- Potential unused monthly spend

Formula:

`unused seats = purchased seats - active seats`

`unused monthly spend = unused seats × cost per seat`

A renewal review call can ask the owner whether to renew as-is, reduce seats, or cancel, then update the database with the result.

### Analytics
- Employee status breakdown
- Call completion rate
- Calls by pillar
- Monthly software spend
- Potential unused software spend
- Overall software utilization

### Call Log
Every call stores:
- Call ID
- Operational pillar
- Entity
- Action
- Status
- Summary
- Transcript
- Structured result
- Timestamp
- Dry-run/live mode

## Dummy data

Edit `data/seed.json` to change the demo company, employees, customers, software, meetings, memos, policies and settings.

Then regenerate the SQLite database:

```bash
python scripts/seed_db.py
```

The database is stored at:

```text
data/relay.db
```

The dummy people intentionally use non-Indian names.

## Run locally

### Backend

```bash
pip install -r requirements.txt
python -m backend.app
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown by the terminal.

## CALL-E

The demo runs in dry-run mode when no CALL-E API key is configured. This lets the entire product flow work locally: trigger call → simulated conversation → structured result → SQLite update → dashboard/call log update.

For live calls, configure `.env`:

```env
CALLE_API_KEY=your_key_here
CALLE_DRY_RUN=false
CALLE_BASE_URL=https://api.heycall-e.com
FLASK_PORT=5000
```

The Flask server keeps the CALL-E API key out of the React frontend.
