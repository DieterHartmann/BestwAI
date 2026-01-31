# BestwAI Raffle Platform

A web-based raffle system for live AI exhibit demos. Users sign up with their name and phone, place wagers, and admin verifies payments before entries become active.

## Features

- **User Signup**: Name, phone, wager amount (multiples of $10)
- **Payment Verification**: Admin manually verifies payments before entry is active
- **QR Code on Display**: Big screen shows QR code for easy signup
- **Automated Hourly Draws**: Configurable raffle intervals
- **Weighted Random Selection**: More entries (higher wager) = higher chance to win
- **5 Winners per Draw**: 40%, 25%, 18%, 10%, 7% distribution
- **10% House Edge**: Platform retains 10% of each pot

## Pages

| Route | Description |
|-------|-------------|
| `/` | User signup page - enter name, phone, wager amount |
| `/display` | Public display screen - QR code, countdown, winner animations |
| `/admin` | Admin panel - verify payments, trigger draws, manage system |

## Flow

1. **Display Screen** (`/display`) shows QR code on big screen
2. **User Scans QR** → lands on signup page (`/`)
3. **User Submits** name, phone, and wager amount
4. **Admin Receives** notification of pending entry
5. **User Pays** admin (cash, Venmo, etc.)
6. **Admin Verifies** payment in admin panel → entry becomes active
7. **Draw Happens** automatically or manually triggered
8. **Winners Announced** with celebration animation

## Quick Start

### Local Development

```bash
# Create and activate conda environment
conda create -n bestwai python=3.11 -y
conda activate bestwai

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

Visit `http://localhost:8080` in your browser.

### Railway Deployment

1. Push this repo to GitHub
2. Connect to Railway
3. Railway will auto-detect and deploy
4. Share the `/display` URL on a big screen
5. Users scan QR code to join

## API Endpoints

### Public API

- `POST /api/signup` - Register for raffle (name, phone, wager)
- `GET /api/raffle/current` - Current raffle status
- `GET /api/raffle/history` - Recent draw history

### Admin API

- `GET /api/admin/participants` - List all participants
- `GET /api/admin/participants/pending` - List unverified entries
- `POST /api/admin/participants/<id>/verify` - Verify payment & add to raffle
- `POST /api/admin/participants/<id>/reject` - Reject entry
- `POST /api/raffle/draw` - Manually trigger draw
- `POST /api/admin/reset` - Reset entire system

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Draw Interval | 60 min | Time between automated draws |
| Min Wager | $10 | Minimum entry amount |
| Max Wager | $1000 | Maximum entry amount |

## Prize Distribution

From 90% of total pot (10% house edge):

| Place | Share |
|-------|-------|
| 🥇 1st | 40% |
| 🥈 2nd | 25% |
| 🥉 3rd | 18% |
| 4th | 10% |
| 5th | 7% |

## Tech Stack

- **Backend**: Flask + SQLAlchemy
- **Database**: SQLite
- **Scheduler**: APScheduler
- **Frontend**: Vanilla JS + CSS
- **QR Codes**: qrcode + Pillow
- **Production**: Gunicorn + Railway

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | Server port |
| `SECRET_KEY` | (generated) | Flask secret key |
| `DATABASE_URL` | sqlite:///raffle.db | Database connection |

## License

MIT - Built for live AI demos.
