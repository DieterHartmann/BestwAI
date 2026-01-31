# BestwAI Raffle Platform

A web-based raffle system for live AI exhibit demos. Attendees use tokens to enter hourly drawings, with winners selected via weighted random selection.

## Features

- **Token System**: Unique alphanumeric token IDs with balances
- **Automated Hourly Draws**: Configurable raffle intervals
- **Weighted Random Selection**: More entries = higher chance to win
- **5 Winners per Draw**: 40%, 25%, 18%, 10%, 7% distribution
- **10% House Edge**: Platform retains 10% of each pot
- **QR Code Support**: Generate printable token cards
- **Real-time Updates**: Live countdown and participant tracking
- **Draw Animation**: Visual celebration when winners are announced

## Pages

| Route | Description |
|-------|-------------|
| `/` | User entry page - check balance, enter raffles |
| `/display` | Public display screen - countdown, pot, winner animations |
| `/admin` | Admin panel - generate tokens, configure settings, trigger draws |

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

The app uses SQLite which works with Railway's ephemeral filesystem for demos.

## Configuration

Default settings (configurable via admin panel):

| Setting | Default | Description |
|---------|---------|-------------|
| Entry Cost | 10 tokens | Cost per raffle entry |
| Draw Interval | 60 minutes | Time between automated draws |
| Starting Balance | 100 tokens | New token default balance |
| Winner Count | 5 | Number of winners per draw |

## API Endpoints

### Public API

- `GET /api/token/<token_id>` - Get token balance and stats
- `GET /api/raffle/current` - Current raffle status
- `POST /api/raffle/enter` - Enter current raffle
- `GET /api/raffle/history` - Recent draw history

### Admin API

- `GET /api/admin/tokens` - List all tokens
- `POST /api/admin/tokens/generate` - Generate new tokens
- `POST /api/admin/tokens/<id>/balance` - Update token balance
- `GET /api/admin/config` - Get configuration
- `POST /api/admin/config` - Update configuration
- `POST /api/raffle/draw` - Manually trigger draw
- `POST /api/admin/reset` - Reset entire system

## Demo Flow

1. **Setup**: Admin generates tokens via `/admin`
2. **Distribution**: Print token cards with QR codes
3. **Entry**: Attendees scan QR → land on entry page
4. **Participation**: Users enter raffle with their tokens
5. **Display**: Show `/display` on big screen for countdown
6. **Draw**: Winners announced with animation
7. **Repeat**: Next raffle starts automatically

## Tech Stack

- **Backend**: Flask + SQLAlchemy
- **Database**: SQLite
- **Scheduler**: APScheduler
- **Frontend**: Vanilla JS + CSS
- **QR Codes**: qrcode + Pillow
- **Production**: Gunicorn

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8080 | Server port |
| `SECRET_KEY` | (generated) | Flask secret key |
| `DATABASE_URL` | sqlite:///raffle.db | Database connection |

## License

MIT - Built for live AI demos.
