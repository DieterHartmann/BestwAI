"""
BestwAI Raffle Platform
A web-based raffle system for live AI exhibit demos.
Users sign up with name, phone, and wager amount. Admin verifies payments.
"""

import os
import random
import string
import secrets
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import qrcode
import io
import base64

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Database configuration - support both SQLite and PostgreSQL
database_url = os.environ.get('DATABASE_URL', 'sqlite:///raffle.db')
# Railway uses postgres:// but SQLAlchemy needs postgresql://
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# =============================================================================
# Configuration (can be modified via admin panel)
# =============================================================================
class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(200), nullable=False)

def get_config(key, default=None):
    """Get configuration value from database."""
    config = Config.query.filter_by(key=key).first()
    return config.value if config else default

def set_config(key, value):
    """Set configuration value in database."""
    config = Config.query.filter_by(key=key).first()
    if config:
        config.value = str(value)
    else:
        config = Config(key=key, value=str(value))
        db.session.add(config)
    db.session.commit()

# =============================================================================
# Database Models
# =============================================================================
class Participant(db.Model):
    """A user who has signed up for the raffle."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    wager_amount = db.Column(db.Integer, nullable=False)  # Must be multiple of 10
    verified = db.Column(db.Boolean, default=False)  # Admin verifies payment
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    entries = db.relationship('Entry', backref='participant', lazy='dynamic')
    wins = db.relationship('Winner', backref='participant', lazy='dynamic')

class Raffle(db.Model):
    """Represents a raffle draw."""
    id = db.Column(db.Integer, primary_key=True)
    draw_time = db.Column(db.DateTime, nullable=False)
    total_pot = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, drawing, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    entries = db.relationship('Entry', backref='raffle', lazy='dynamic')
    winners = db.relationship('Winner', backref='raffle', lazy='dynamic')

class Entry(db.Model):
    """Represents entries into a raffle."""
    id = db.Column(db.Integer, primary_key=True)
    raffle_id = db.Column(db.Integer, db.ForeignKey('raffle.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False)
    entry_count = db.Column(db.Integer, default=1)  # Based on wager amount
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Winner(db.Model):
    """Represents raffle winners."""
    id = db.Column(db.Integer, primary_key=True)
    raffle_id = db.Column(db.Integer, db.ForeignKey('raffle.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False)
    amount_won = db.Column(db.Integer, nullable=False)
    position = db.Column(db.Integer, nullable=False)  # 1st, 2nd, 3rd, etc.
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class TelegramMessage(db.Model):
    """Stores messages from Telegram bot."""
    id = db.Column(db.Integer, primary_key=True)
    telegram_user_id = db.Column(db.BigInteger, nullable=False)
    username = db.Column(db.String(100))
    first_name = db.Column(db.String(100))
    message_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# =============================================================================
# Helper Functions
# =============================================================================
def generate_qr_code(data):
    """Generate a QR code as base64 string."""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()

def get_current_raffle():
    """Get or create the current pending raffle."""
    raffle = Raffle.query.filter_by(status='pending').first()
    if not raffle:
        # Create new raffle with next draw time at :00 or :30 (every 30 min)
        # Using UTC+2 timezone (South Africa / SAST)
        UTC_OFFSET = 2  # UTC+2
        
        now_utc = datetime.utcnow()
        now_local = now_utc + timedelta(hours=UTC_OFFSET)
        
        # Find next :00 or :30 in local time
        if now_local.minute < 30:
            # Next is :30 this hour
            next_draw_local = now_local.replace(minute=30, second=0, microsecond=0)
        else:
            # Next is :00 next hour
            next_draw_local = now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        # Convert back to UTC for storage
        next_draw_utc = next_draw_local - timedelta(hours=UTC_OFFSET)
        
        raffle = Raffle(draw_time=next_draw_utc, status='pending')
        db.session.add(raffle)
        db.session.commit()
        
        # Auto-add ALL verified participants to new raffle
        verified_participants = Participant.query.filter_by(verified=True).all()
        for participant in verified_participants:
            entry_count = participant.wager_amount // 10
            entry = Entry(
                raffle_id=raffle.id,
                participant_id=participant.id,
                entry_count=entry_count
            )
            db.session.add(entry)
            raffle.total_pot += participant.wager_amount
        db.session.commit()
        
    return raffle

def add_verified_participant_to_raffle(participant):
    """Add a verified participant to the current raffle."""
    raffle = get_current_raffle()
    
    # Check if already entered
    existing = Entry.query.filter_by(raffle_id=raffle.id, participant_id=participant.id).first()
    if existing:
        return False
    
    # Calculate entries (1 entry per 10 wagered)
    entry_count = participant.wager_amount // 10
    
    # Create entry
    entry = Entry(
        raffle_id=raffle.id,
        participant_id=participant.id,
        entry_count=entry_count
    )
    db.session.add(entry)
    
    # Update pot
    raffle.total_pot += participant.wager_amount
    db.session.commit()
    
    return True

def execute_raffle_draw(raffle_id=None):
    """Execute the raffle draw and select winners."""
    with app.app_context():
        if raffle_id:
            raffle = Raffle.query.get(raffle_id)
        else:
            raffle = Raffle.query.filter_by(status='pending').first()
        
        if not raffle or raffle.status != 'pending':
            return None
        
        # Mark as drawing
        raffle.status = 'drawing'
        db.session.commit()
        
        # Get all entries for this raffle
        entries = Entry.query.filter_by(raffle_id=raffle.id).all()
        
        if not entries:
            raffle.status = 'completed'
            db.session.commit()
            get_current_raffle()
            return {'winners': [], 'pot': 0, 'raffle_id': raffle.id}
        
        # Build weighted list of participant IDs
        weighted_entries = []
        for entry in entries:
            weighted_entries.extend([entry.participant_id] * entry.entry_count)
        
        # Calculate payouts
        total_pot = raffle.total_pot
        house_cut = int(total_pot * 0.20)  # 20% house edge
        prize_pool = total_pot - house_cut
        
        # Winner distribution (2 winners: 50% first, 30% second)
        unique_participants = list(set(weighted_entries))
        winner_count = min(2, len(unique_participants))
        
        if winner_count == 0:
            raffle.status = 'completed'
            db.session.commit()
            get_current_raffle()
            return {'winners': [], 'pot': 0, 'raffle_id': raffle.id}
        
        # Distribution: 50% to 1st, 30% to 2nd (of the 80% prize pool)
        # This means: 1st gets 50/80 = 62.5% of prize pool, 2nd gets 30/80 = 37.5%
        distributions = [0.625, 0.375][:winner_count]
        if winner_count == 1:
            distributions = [1.0]  # Single winner gets entire prize pool
        
        # Select winners (weighted random, no duplicates)
        winners_data = []
        selected_ids = set()
        remaining_entries = weighted_entries.copy()
        
        for position, dist in enumerate(distributions, 1):
            if not remaining_entries:
                break
            
            # Select winner
            winner_id = random.choice(remaining_entries)
            
            # Avoid duplicates
            attempts = 0
            while winner_id in selected_ids and attempts < 100:
                remaining_entries = [e for e in remaining_entries if e != winner_id]
                if not remaining_entries:
                    break
                winner_id = random.choice(remaining_entries)
                attempts += 1
            
            if winner_id in selected_ids:
                continue
                
            participant = Participant.query.get(winner_id)
            if not participant:
                continue
            
            selected_ids.add(winner_id)
            amount = int(prize_pool * dist)
            
            # Create winner record
            winner = Winner(
                raffle_id=raffle.id,
                participant_id=participant.id,
                amount_won=amount,
                position=position
            )
            db.session.add(winner)
            
            winners_data.append({
                'name': participant.name,
                'phone_last4': participant.phone[-4:] if len(participant.phone) >= 4 else participant.phone,
                'amount': amount,
                'position': position
            })
            
            # Remove this participant from remaining
            remaining_entries = [e for e in remaining_entries if e != winner_id]
        
        # Complete the raffle
        raffle.status = 'completed'
        db.session.commit()
        
        # Create next raffle
        get_current_raffle()
        
        return {
            'winners': winners_data,
            'pot': total_pot,
            'house_cut': house_cut,
            'raffle_id': raffle.id
        }

# =============================================================================
# Routes - User Pages
# =============================================================================
@app.route('/')
def index():
    """Signup page for users."""
    return render_template('index.html')

@app.route('/display')
def display():
    """Public display screen with QR code for signup."""
    # Generate QR code for signup URL
    base_url = request.url_root.rstrip('/')
    signup_url = base_url + '/'
    qr_code = generate_qr_code(signup_url)
    return render_template('display.html', qr_code=qr_code, signup_url=signup_url)

@app.route('/admin')
def admin():
    """Admin panel for verification and management."""
    return render_template('admin.html')

@app.route('/success')
def success():
    """Success page after signup."""
    return render_template('success.html')

# =============================================================================
# API Routes
# =============================================================================
@app.route('/api/signup', methods=['POST'])
def signup():
    """Register a new participant with PIN verification."""
    data = request.json
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    wager = data.get('wager', 0)
    pin = data.get('pin', '').strip()
    
    # Validation
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    if not phone:
        return jsonify({'error': 'Phone number is required'}), 400
    if not wager or wager < 10:
        return jsonify({'error': 'Minimum wager is $10'}), 400
    if wager % 10 != 0:
        return jsonify({'error': 'Wager must be in multiples of $10'}), 400
    
    # PIN validation - admin must enter their PIN
    admin_pin = get_config('admin_pin', '1234')  # Default PIN is 1234
    if pin != admin_pin:
        return jsonify({'error': 'Invalid PIN. Ask admin to enter the PIN.'}), 403
    
    # Check if phone already exists
    raffle = get_current_raffle()
    existing = Participant.query.filter_by(phone=phone).first()
    
    if existing:
        # Add to existing participant's wager
        existing.wager_amount += wager
        existing.name = name  # Update name in case it changed
        db.session.commit()
        
        # Update their entry in current raffle
        entry = Entry.query.filter_by(raffle_id=raffle.id, participant_id=existing.id).first()
        if entry:
            # Add more entries
            new_entries = wager // 10
            entry.entry_count += new_entries
            raffle.total_pot += wager
            db.session.commit()
        else:
            # Not in this raffle yet, add them
            add_verified_participant_to_raffle(existing)
        
        total_chances = existing.wager_amount // 10
        return jsonify({
            'success': True,
            'participant_id': existing.id,
            'message': f'Added ${wager} more! {name} now has ${existing.wager_amount} total with {total_chances} chances to win!'
        })
    
    # Create new participant (auto-verified since PIN was correct)
    participant = Participant(
        name=name,
        phone=phone,
        wager_amount=wager,
        verified=True  # Auto-verify on correct PIN
    )
    db.session.add(participant)
    db.session.commit()
    
    # Add directly to raffle since verified
    add_verified_participant_to_raffle(participant)
    
    return jsonify({
        'success': True,
        'participant_id': participant.id,
        'message': f'Welcome {name}! Your ${wager} entry is confirmed with {wager // 10} chances to win!'
    })

@app.route('/api/raffle/current')
def get_current_raffle_info():
    """Get current raffle status."""
    raffle = get_current_raffle()
    
    # Get verified participants only
    entries = Entry.query.filter_by(raffle_id=raffle.id).all()
    participants = []
    total_entries = 0
    
    for entry in entries:
        participant = Participant.query.get(entry.participant_id)
        if participant and participant.verified:
            # Show partial name for privacy
            display_name = participant.name.split()[0] if participant.name else 'Anonymous'
            if len(display_name) > 8:
                display_name = display_name[:8] + '...'
            participants.append({
                'name': display_name,
                'entries': entry.entry_count,
                'wager': participant.wager_amount
            })
            total_entries += entry.entry_count
    
    return jsonify({
        'raffle_id': raffle.id,
        'status': raffle.status,
        'draw_time': raffle.draw_time.isoformat() + 'Z',  # Z indicates UTC
        'total_pot': raffle.total_pot,
        'participant_count': len(participants),
        'total_entries': total_entries,
        'participants': participants,
        'server_time': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/api/raffle/draw', methods=['POST'])
def trigger_draw():
    """Manually trigger raffle draw (admin only)."""
    result = execute_raffle_draw()
    if result:
        return jsonify(result)
    return jsonify({'error': 'No active raffle to draw'}), 400

@app.route('/api/raffle/reset-timer', methods=['POST'])
def reset_timer():
    """Reset the current raffle's draw time to next :00 or :30."""
    raffle = Raffle.query.filter_by(status='pending').first()
    if not raffle:
        return jsonify({'error': 'No pending raffle'}), 400
    
    UTC_OFFSET = 2  # UTC+2
    now_utc = datetime.utcnow()
    now_local = now_utc + timedelta(hours=UTC_OFFSET)
    
    # Find next :00 or :30 in local time
    if now_local.minute < 30:
        next_draw_local = now_local.replace(minute=30, second=0, microsecond=0)
    else:
        next_draw_local = now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    
    # Convert back to UTC for storage
    next_draw_utc = next_draw_local - timedelta(hours=UTC_OFFSET)
    
    raffle.draw_time = next_draw_utc
    db.session.commit()
    
    return jsonify({
        'success': True,
        'new_draw_time': raffle.draw_time.isoformat() + 'Z',
        'local_time': next_draw_local.strftime('%H:%M')
    })

@app.route('/api/raffle/history')
def get_raffle_history():
    """Get recent raffle history."""
    limit = request.args.get('limit', 5, type=int)
    raffles = Raffle.query.filter_by(status='completed').order_by(Raffle.draw_time.desc()).limit(limit).all()
    
    history = []
    for raffle in raffles:
        winners = Winner.query.filter_by(raffle_id=raffle.id).order_by(Winner.position).all()
        history.append({
            'raffle_id': raffle.id,
            'draw_time': raffle.draw_time.isoformat(),
            'total_pot': raffle.total_pot,
            'winners': [{
                'name': Participant.query.get(w.participant_id).name.split()[0] if Participant.query.get(w.participant_id) else 'Unknown',
                'amount': w.amount_won,
                'position': w.position
            } for w in winners]
        })
    
    return jsonify(history)

@app.route('/api/raffle/latest-winners')
def get_latest_winners():
    """Get winners from the most recent completed raffle."""
    raffle = Raffle.query.filter_by(status='completed').order_by(Raffle.draw_time.desc()).first()
    if not raffle:
        return jsonify({'winners': [], 'raffle_id': None})
    
    winners = Winner.query.filter_by(raffle_id=raffle.id).order_by(Winner.position).all()
    return jsonify({
        'raffle_id': raffle.id,
        'draw_time': raffle.draw_time.isoformat(),
        'total_pot': raffle.total_pot,
        'winners': [{
            'name': Participant.query.get(w.participant_id).name if Participant.query.get(w.participant_id) else 'Unknown',
            'amount': w.amount_won,
            'position': w.position
        } for w in winners]
    })

# =============================================================================
# Telegram Bot Integration
# =============================================================================
@app.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """Receive messages from Telegram bot."""
    data = request.json
    
    if not data:
        return jsonify({'ok': True})
    
    # Extract message info
    message = data.get('message', {})
    if not message:
        return jsonify({'ok': True})
    
    text = message.get('text', '')
    if not text:
        return jsonify({'ok': True})
    
    user = message.get('from', {})
    telegram_user_id = user.get('id')
    username = user.get('username', '')
    first_name = user.get('first_name', 'Anonymous')
    
    # Save message to database
    msg = TelegramMessage(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        message_text=text[:500]  # Limit message length
    )
    db.session.add(msg)
    db.session.commit()
    
    # Send confirmation back to user
    if TELEGRAM_BOT_TOKEN:
        chat_id = message.get('chat', {}).get('id')
        send_telegram_message(chat_id, f"✅ Message received: \"{text[:50]}...\" - displayed on screen!")
    
    return jsonify({'ok': True})

def send_telegram_message(chat_id, text):
    """Send a message to a Telegram chat."""
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={'chat_id': chat_id, 'text': text}, timeout=5)
    except:
        pass

@app.route('/api/telegram/messages')
def get_telegram_messages():
    """Get recent Telegram messages."""
    limit = request.args.get('limit', 10, type=int)
    messages = TelegramMessage.query.order_by(TelegramMessage.timestamp.desc()).limit(limit).all()
    
    return jsonify([{
        'id': m.id,
        'username': m.username or m.first_name,
        'message': m.message_text,
        'timestamp': m.timestamp.isoformat() + 'Z'
    } for m in messages])

@app.route('/api/telegram/setup-webhook', methods=['POST'])
def setup_telegram_webhook():
    """Set up the Telegram webhook (call once after deploy)."""
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({'error': 'TELEGRAM_BOT_TOKEN not set'}), 400
    
    # Get the public URL - force HTTPS
    webhook_url = request.url_root.rstrip('/').replace('http://', 'https://') + '/telegram/webhook'
    
    # Set webhook with Telegram
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    response = requests.post(url, json={'url': webhook_url}, timeout=10)
    
    return jsonify({
        'webhook_url': webhook_url,
        'telegram_response': response.json()
    })

@app.route('/api/telegram/bot-info')
def get_telegram_bot_info():
    """Get bot info and QR code link."""
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({'error': 'TELEGRAM_BOT_TOKEN not set'}), 400
    
    # Get bot username
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
    try:
        response = requests.get(url, timeout=5)
        bot_data = response.json()
        if bot_data.get('ok'):
            bot_username = bot_data['result'].get('username', '')
            bot_link = f"https://t.me/{bot_username}"
            qr_code = generate_qr_code(bot_link)
            return jsonify({
                'bot_username': bot_username,
                'bot_link': bot_link,
                'qr_code': qr_code
            })
    except:
        pass
    
    return jsonify({'error': 'Could not get bot info'}), 500

# =============================================================================
# Admin API Routes
# =============================================================================
@app.route('/api/admin/participants')
def list_participants():
    """List all participants (pending and verified)."""
    raffle = get_current_raffle()
    
    # Get participants for current raffle
    participants = Participant.query.order_by(Participant.created_at.desc()).all()
    
    result = []
    for p in participants:
        # Check if in current raffle
        entry = Entry.query.filter_by(raffle_id=raffle.id, participant_id=p.id).first()
        result.append({
            'id': p.id,
            'name': p.name,
            'phone': p.phone,
            'wager': p.wager_amount,
            'verified': p.verified,
            'in_current_raffle': entry is not None,
            'created_at': p.created_at.isoformat()
        })
    
    return jsonify(result)

@app.route('/api/admin/participants/pending')
def list_pending_participants():
    """List unverified participants."""
    participants = Participant.query.filter_by(verified=False).order_by(Participant.created_at.desc()).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'phone': p.phone,
        'wager': p.wager_amount,
        'created_at': p.created_at.isoformat()
    } for p in participants])

@app.route('/api/admin/participants/<int:participant_id>/verify', methods=['POST'])
def verify_participant(participant_id):
    """Verify a participant's payment and add them to raffle."""
    participant = Participant.query.get(participant_id)
    if not participant:
        return jsonify({'error': 'Participant not found'}), 404
    
    if participant.verified:
        return jsonify({'error': 'Already verified'}), 400
    
    # Mark as verified
    participant.verified = True
    db.session.commit()
    
    # Add to current raffle
    added = add_verified_participant_to_raffle(participant)
    
    return jsonify({
        'success': True,
        'message': f'{participant.name} verified and added to raffle!',
        'added_to_raffle': added
    })

@app.route('/api/admin/participants/<int:participant_id>/reject', methods=['POST'])
def reject_participant(participant_id):
    """Reject/delete a participant."""
    participant = Participant.query.get(participant_id)
    if not participant:
        return jsonify({'error': 'Participant not found'}), 404
    
    # Remove any entries
    Entry.query.filter_by(participant_id=participant_id).delete()
    
    # Delete participant
    db.session.delete(participant)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Participant removed'})

@app.route('/api/admin/config', methods=['GET'])
def get_all_config():
    """Get all configuration."""
    return jsonify({
        'draw_interval': int(get_config('draw_interval', 60)),
        'min_wager': int(get_config('min_wager', 10)),
        'max_wager': int(get_config('max_wager', 1000)),
        'admin_pin': get_config('admin_pin', '1234')
    })

@app.route('/api/admin/config', methods=['POST'])
def update_config():
    """Update configuration."""
    data = request.json
    for key, value in data.items():
        set_config(key, value)
    return jsonify({'success': True})

@app.route('/api/admin/reset', methods=['POST'])
def reset_system():
    """Reset the entire system."""
    Winner.query.delete()
    Entry.query.delete()
    Raffle.query.delete()
    Participant.query.delete()
    db.session.commit()
    
    get_current_raffle()
    
    return jsonify({'success': True, 'message': 'System reset complete'})

@app.route('/api/debug')
def debug_database():
    """Debug endpoint to check database contents."""
    raffle = get_current_raffle()
    
    participants = Participant.query.all()
    entries = Entry.query.filter_by(raffle_id=raffle.id).all()
    
    # Check all database-related env vars
    env_vars = {}
    for key in os.environ:
        if 'DATABASE' in key.upper() or 'PG' in key.upper() or 'POSTGRES' in key.upper():
            val = os.environ[key]
            # Mask password in URL
            if 'postgresql://' in val or 'postgres://' in val:
                env_vars[key] = val[:30] + '...[masked]'
            else:
                env_vars[key] = val[:50] if len(val) > 50 else val
    
    # Show ALL env var names (not values) to help debug
    all_env_keys = sorted([k for k in os.environ.keys()])
    
    return jsonify({
        'database_url_configured': app.config['SQLALCHEMY_DATABASE_URI'][:30] + '...',
        'env_database_url': os.environ.get('DATABASE_URL', 'NOT SET')[:30] + '...' if os.environ.get('DATABASE_URL') else 'NOT SET',
        'all_db_env_vars': env_vars,
        'all_env_keys': all_env_keys,
        'raffle': {
            'id': raffle.id,
            'status': raffle.status,
            'total_pot': raffle.total_pot,
            'draw_time': raffle.draw_time.isoformat()
        },
        'total_participants': len(participants),
        'participants': [{
            'id': p.id,
            'name': p.name,
            'wager': p.wager_amount,
            'verified': p.verified
        } for p in participants],
        'entries_in_raffle': len(entries),
        'entries': [{
            'participant_id': e.participant_id,
            'entry_count': e.entry_count
        } for e in entries]
    })

# =============================================================================
# Scheduler for Automated Draws
# =============================================================================
scheduler = BackgroundScheduler()

def check_and_execute_draw():
    """Check if it's time for a draw and execute it."""
    with app.app_context():
        raffle = Raffle.query.filter_by(status='pending').first()
        if raffle and datetime.utcnow() >= raffle.draw_time:
            execute_raffle_draw(raffle.id)

# =============================================================================
# Initialize Application
# =============================================================================
def init_db():
    """Initialize database and default configuration."""
    with app.app_context():
        db.create_all()
        
        # Set default configuration
        if not get_config('draw_interval'):
            set_config('draw_interval', 60)
        if not get_config('min_wager'):
            set_config('min_wager', 10)
        if not get_config('max_wager'):
            set_config('max_wager', 1000)
        if not get_config('admin_pin'):
            set_config('admin_pin', '1234')
        
        get_current_raffle()

# Initialize on startup
with app.app_context():
    init_db()

# Start scheduler
scheduler.add_job(check_and_execute_draw, 'interval', seconds=10)
scheduler.start()

# =============================================================================
# Run Application
# =============================================================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
