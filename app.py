"""
BestwAI Raffle Platform
A web-based raffle system for live AI exhibit demos.
"""

import os
import random
import string
import secrets
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import qrcode
import io
import base64

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///raffle.db')
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
class Token(db.Model):
    """Represents a user's token with balance."""
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    balance = db.Column(db.Integer, default=100, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    entries = db.relationship('Entry', backref='token', lazy='dynamic')
    wins = db.relationship('Winner', backref='token', lazy='dynamic')

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
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False)
    entry_count = db.Column(db.Integer, default=1)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Winner(db.Model):
    """Represents raffle winners."""
    id = db.Column(db.Integer, primary_key=True)
    raffle_id = db.Column(db.Integer, db.ForeignKey('raffle.id'), nullable=False)
    token_id = db.Column(db.Integer, db.ForeignKey('token.id'), nullable=False)
    amount_won = db.Column(db.Integer, nullable=False)
    position = db.Column(db.Integer, nullable=False)  # 1st, 2nd, 3rd, etc.
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# =============================================================================
# Helper Functions
# =============================================================================
def generate_token_id():
    """Generate a unique token ID like TKN-A1B2C3."""
    chars = string.ascii_uppercase + string.digits
    while True:
        token_id = 'TKN-' + ''.join(random.choices(chars, k=6))
        if not Token.query.filter_by(token_id=token_id).first():
            return token_id

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
        # Create new raffle with next draw time
        interval = int(get_config('draw_interval', 60))  # minutes
        next_draw = datetime.utcnow() + timedelta(minutes=interval)
        raffle = Raffle(draw_time=next_draw, status='pending')
        db.session.add(raffle)
        db.session.commit()
    return raffle

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
            # Create next raffle
            get_current_raffle()
            return {'winners': [], 'pot': 0, 'raffle_id': raffle.id}
        
        # Build weighted list of token IDs
        weighted_entries = []
        for entry in entries:
            weighted_entries.extend([entry.token_id] * entry.entry_count)
        
        # Calculate payouts
        total_pot = raffle.total_pot
        house_cut = int(total_pot * 0.10)  # 10% house edge
        prize_pool = total_pot - house_cut
        
        # Winner distribution (5 winners)
        winner_count = min(5, len(set(weighted_entries)))
        if winner_count == 0:
            raffle.status = 'completed'
            db.session.commit()
            get_current_raffle()
            return {'winners': [], 'pot': 0, 'raffle_id': raffle.id}
        
        # Distribution percentages for 5 winners: 40%, 25%, 18%, 10%, 7%
        distributions = [0.40, 0.25, 0.18, 0.10, 0.07][:winner_count]
        # Normalize if fewer winners
        total_dist = sum(distributions)
        distributions = [d / total_dist for d in distributions]
        
        # Select winners (weighted random, no duplicates for positions)
        winners_data = []
        selected_token_ids = set()
        remaining_entries = weighted_entries.copy()
        
        for position, dist in enumerate(distributions, 1):
            if not remaining_entries:
                break
            
            # Select winner
            winner_token_db_id = random.choice(remaining_entries)
            token = Token.query.get(winner_token_db_id)
            
            if token.id in selected_token_ids:
                # Remove this token from remaining and try again
                remaining_entries = [e for e in remaining_entries if e != winner_token_db_id]
                if remaining_entries:
                    winner_token_db_id = random.choice(remaining_entries)
                    token = Token.query.get(winner_token_db_id)
                else:
                    break
            
            selected_token_ids.add(token.id)
            amount = int(prize_pool * dist)
            
            # Create winner record
            winner = Winner(
                raffle_id=raffle.id,
                token_id=token.id,
                amount_won=amount,
                position=position
            )
            db.session.add(winner)
            
            # Credit winner's balance
            token.balance += amount
            
            winners_data.append({
                'token_id': token.token_id,
                'amount': amount,
                'position': position
            })
            
            # Remove this token from remaining entries for next selection
            remaining_entries = [e for e in remaining_entries if e != winner_token_db_id]
        
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
    """Main user entry page."""
    token_id = request.args.get('token', '')
    return render_template('index.html', token_id=token_id)

@app.route('/display')
def display():
    """Public display screen for live viewing."""
    return render_template('display.html')

@app.route('/admin')
def admin():
    """Admin panel."""
    return render_template('admin.html')

# =============================================================================
# API Routes
# =============================================================================
@app.route('/api/token/<token_id>')
def get_token_info(token_id):
    """Get token balance and info."""
    token = Token.query.filter_by(token_id=token_id.upper()).first()
    if not token:
        return jsonify({'error': 'Token not found'}), 404
    
    # Get entry count for current raffle
    raffle = get_current_raffle()
    entry = Entry.query.filter_by(raffle_id=raffle.id, token_id=token.id).first()
    
    return jsonify({
        'token_id': token.token_id,
        'balance': token.balance,
        'current_entries': entry.entry_count if entry else 0,
        'total_wins': token.wins.count(),
        'total_winnings': sum(w.amount_won for w in token.wins)
    })

@app.route('/api/raffle/current')
def get_current_raffle_info():
    """Get current raffle status."""
    raffle = get_current_raffle()
    
    # Get participant info
    entries = Entry.query.filter_by(raffle_id=raffle.id).all()
    participants = []
    total_entries = 0
    
    for entry in entries:
        token = Token.query.get(entry.token_id)
        participants.append({
            'token_id': token.token_id,
            'entries': entry.entry_count
        })
        total_entries += entry.entry_count
    
    entry_cost = int(get_config('entry_cost', 10))
    
    return jsonify({
        'raffle_id': raffle.id,
        'status': raffle.status,
        'draw_time': raffle.draw_time.isoformat(),
        'total_pot': raffle.total_pot,
        'participant_count': len(participants),
        'total_entries': total_entries,
        'participants': participants,
        'entry_cost': entry_cost,
        'server_time': datetime.utcnow().isoformat()
    })

@app.route('/api/raffle/enter', methods=['POST'])
def enter_raffle():
    """Enter current raffle with tokens."""
    data = request.json
    token_id = data.get('token_id', '').upper()
    entries = data.get('entries', 1)
    
    token = Token.query.filter_by(token_id=token_id).first()
    if not token:
        return jsonify({'error': 'Token not found'}), 404
    
    entry_cost = int(get_config('entry_cost', 10))
    total_cost = entry_cost * entries
    
    if token.balance < total_cost:
        return jsonify({'error': 'Insufficient balance'}), 400
    
    raffle = get_current_raffle()
    if raffle.status != 'pending':
        return jsonify({'error': 'Raffle not accepting entries'}), 400
    
    # Deduct tokens
    token.balance -= total_cost
    
    # Add to pot
    raffle.total_pot += total_cost
    
    # Create or update entry
    entry = Entry.query.filter_by(raffle_id=raffle.id, token_id=token.id).first()
    if entry:
        entry.entry_count += entries
    else:
        entry = Entry(raffle_id=raffle.id, token_id=token.id, entry_count=entries)
        db.session.add(entry)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'new_balance': token.balance,
        'total_entries': entry.entry_count,
        'pot_size': raffle.total_pot
    })

@app.route('/api/raffle/draw', methods=['POST'])
def trigger_draw():
    """Manually trigger raffle draw (admin only)."""
    result = execute_raffle_draw()
    if result:
        return jsonify(result)
    return jsonify({'error': 'No active raffle to draw'}), 400

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
                'token_id': Token.query.get(w.token_id).token_id,
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
            'token_id': Token.query.get(w.token_id).token_id,
            'amount': w.amount_won,
            'position': w.position
        } for w in winners]
    })

# =============================================================================
# Admin API Routes
# =============================================================================
@app.route('/api/admin/tokens', methods=['GET'])
def list_tokens():
    """List all tokens."""
    tokens = Token.query.order_by(Token.created_at.desc()).all()
    return jsonify([{
        'token_id': t.token_id,
        'balance': t.balance,
        'created_at': t.created_at.isoformat()
    } for t in tokens])

@app.route('/api/admin/tokens/generate', methods=['POST'])
def generate_tokens():
    """Generate new tokens."""
    data = request.json
    count = data.get('count', 1)
    starting_balance = data.get('balance', 100)
    
    base_url = request.url_root
    new_tokens = []
    
    for _ in range(count):
        token_id = generate_token_id()
        token = Token(token_id=token_id, balance=starting_balance)
        db.session.add(token)
        
        # Generate QR code
        url = f"{base_url}?token={token_id}"
        qr_code = generate_qr_code(url)
        
        new_tokens.append({
            'token_id': token_id,
            'balance': starting_balance,
            'url': url,
            'qr_code': qr_code
        })
    
    db.session.commit()
    return jsonify(new_tokens)

@app.route('/api/admin/tokens/<token_id>/balance', methods=['POST'])
def update_token_balance(token_id):
    """Update a token's balance."""
    data = request.json
    new_balance = data.get('balance')
    
    token = Token.query.filter_by(token_id=token_id.upper()).first()
    if not token:
        return jsonify({'error': 'Token not found'}), 404
    
    token.balance = new_balance
    db.session.commit()
    
    return jsonify({'token_id': token.token_id, 'balance': token.balance})

@app.route('/api/admin/config', methods=['GET'])
def get_all_config():
    """Get all configuration."""
    return jsonify({
        'entry_cost': int(get_config('entry_cost', 10)),
        'draw_interval': int(get_config('draw_interval', 60)),
        'starting_balance': int(get_config('starting_balance', 100)),
        'winner_count': int(get_config('winner_count', 5))
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
    # Clear all tables
    Winner.query.delete()
    Entry.query.delete()
    Raffle.query.delete()
    Token.query.delete()
    db.session.commit()
    
    # Create new raffle
    get_current_raffle()
    
    return jsonify({'success': True, 'message': 'System reset complete'})

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
        
        # Set default configuration if not exists
        if not get_config('entry_cost'):
            set_config('entry_cost', 10)
        if not get_config('draw_interval'):
            set_config('draw_interval', 60)
        if not get_config('starting_balance'):
            set_config('starting_balance', 100)
        if not get_config('winner_count'):
            set_config('winner_count', 5)
        
        # Ensure there's a current raffle
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
