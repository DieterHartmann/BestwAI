"""
BestwAI Raffle Platform
A web-based raffle system for live AI exhibit demos.
Users sign up with name, phone, and wager amount. Admin verifies payments.
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
        # Create new raffle with next draw time
        interval = int(get_config('draw_interval', 60))  # minutes
        next_draw = datetime.utcnow() + timedelta(minutes=interval)
        raffle = Raffle(draw_time=next_draw, status='pending')
        db.session.add(raffle)
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
        house_cut = int(total_pot * 0.10)  # 10% house edge
        prize_pool = total_pot - house_cut
        
        # Winner distribution (5 winners max)
        unique_participants = list(set(weighted_entries))
        winner_count = min(5, len(unique_participants))
        
        if winner_count == 0:
            raffle.status = 'completed'
            db.session.commit()
            get_current_raffle()
            return {'winners': [], 'pot': 0, 'raffle_id': raffle.id}
        
        # Distribution percentages for 5 winners: 40%, 25%, 18%, 10%, 7%
        distributions = [0.40, 0.25, 0.18, 0.10, 0.07][:winner_count]
        total_dist = sum(distributions)
        distributions = [d / total_dist for d in distributions]
        
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
    """Register a new participant."""
    data = request.json
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    wager = data.get('wager', 0)
    
    # Validation
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    if not phone:
        return jsonify({'error': 'Phone number is required'}), 400
    if not wager or wager < 10:
        return jsonify({'error': 'Minimum wager is 10'}), 400
    if wager % 10 != 0:
        return jsonify({'error': 'Wager must be in multiples of 10'}), 400
    
    # Check for duplicate phone in current raffle
    raffle = get_current_raffle()
    existing = Participant.query.join(Entry).filter(
        Entry.raffle_id == raffle.id,
        Participant.phone == phone
    ).first()
    
    if existing:
        return jsonify({'error': 'This phone number is already registered for the current raffle'}), 400
    
    # Create participant (unverified)
    participant = Participant(
        name=name,
        phone=phone,
        wager_amount=wager,
        verified=False
    )
    db.session.add(participant)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'participant_id': participant.id,
        'message': f'Registration received! Your entry will be active once payment of {wager} is verified.'
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
        'draw_time': raffle.draw_time.isoformat(),
        'total_pot': raffle.total_pot,
        'participant_count': len(participants),
        'total_entries': total_entries,
        'participants': participants,
        'server_time': datetime.utcnow().isoformat()
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
        'max_wager': int(get_config('max_wager', 1000))
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
