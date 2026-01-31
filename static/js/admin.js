/**
 * BestwAI Raffle - Admin Panel JavaScript
 */

// DOM Elements
const triggerDrawBtn = document.getElementById('triggerDrawBtn');
const resetSystemBtn = document.getElementById('resetSystemBtn');
const refreshBtn = document.getElementById('refreshBtn');
const saveConfigBtn = document.getElementById('saveConfigBtn');

const configAdminPin = document.getElementById('configAdminPin');
const configDrawInterval = document.getElementById('configDrawInterval');
const configMinWager = document.getElementById('configMinWager');
const configMaxWager = document.getElementById('configMaxWager');

const raffleStatus = document.getElementById('raffleStatus');
const rafflePot = document.getElementById('rafflePot');
const raffleParticipants = document.getElementById('raffleParticipants');
const raffleDrawTime = document.getElementById('raffleDrawTime');

const pendingList = document.getElementById('pendingList');
const verifiedList = document.getElementById('verifiedList');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    loadRaffleStatus();
    loadPendingParticipants();
    loadAllParticipants();
    
    // Set up event listeners
    triggerDrawBtn.addEventListener('click', triggerDraw);
    resetSystemBtn.addEventListener('click', resetSystem);
    refreshBtn.addEventListener('click', () => {
        loadPendingParticipants();
        loadAllParticipants();
    });
    saveConfigBtn.addEventListener('click', saveConfig);
    
    // Auto-refresh
    setInterval(loadRaffleStatus, 5000);
    setInterval(loadPendingParticipants, 5000);
});

// Load configuration
async function loadConfig() {
    try {
        const response = await fetch('/api/admin/config');
        const config = await response.json();
        
        configAdminPin.value = config.admin_pin || '1234';
        configDrawInterval.value = config.draw_interval;
        configMinWager.value = config.min_wager;
        configMaxWager.value = config.max_wager;
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

// Save configuration
async function saveConfig() {
    try {
        saveConfigBtn.disabled = true;
        saveConfigBtn.textContent = 'Saving...';
        
        const response = await fetch('/api/admin/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                admin_pin: configAdminPin.value,
                draw_interval: parseInt(configDrawInterval.value),
                min_wager: parseInt(configMinWager.value),
                max_wager: parseInt(configMaxWager.value)
            })
        });
        
        if (response.ok) {
            alert('Configuration saved! PIN: ' + configAdminPin.value);
        } else {
            alert('Error saving configuration');
        }
    } catch (error) {
        console.error('Error saving config:', error);
        alert('Error saving configuration');
    } finally {
        saveConfigBtn.disabled = false;
        saveConfigBtn.textContent = 'Save Configuration';
    }
}

// Load raffle status
async function loadRaffleStatus() {
    try {
        const response = await fetch('/api/raffle/current');
        const data = await response.json();
        
        raffleStatus.textContent = data.status.toUpperCase();
        rafflePot.textContent = `$${data.total_pot}`;
        raffleParticipants.textContent = data.participant_count;
        
        const drawTime = new Date(data.draw_time);
        raffleDrawTime.textContent = drawTime.toLocaleString();
    } catch (error) {
        console.error('Error loading raffle status:', error);
    }
}

// Load pending participants (unverified)
async function loadPendingParticipants() {
    try {
        const response = await fetch('/api/admin/participants/pending');
        const participants = await response.json();
        
        if (participants.length === 0) {
            pendingList.innerHTML = '<p class="no-pending">No pending verifications</p>';
            return;
        }
        
        pendingList.innerHTML = participants.map(p => `
            <div class="pending-item">
                <div class="pending-info">
                    <div class="pending-name">${p.name}</div>
                    <div class="pending-phone">📱 ${p.phone}</div>
                    <div class="pending-wager">💵 $${p.wager}</div>
                    <div class="pending-time">${formatTime(p.created_at)}</div>
                </div>
                <div class="pending-actions">
                    <button class="btn btn-success btn-sm" onclick="verifyParticipant(${p.id})">
                        ✓ Verify Payment
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="rejectParticipant(${p.id})">
                        ✗ Reject
                    </button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading pending participants:', error);
    }
}

// Load all participants (for verified list)
async function loadAllParticipants() {
    try {
        const response = await fetch('/api/admin/participants');
        const participants = await response.json();
        
        const verified = participants.filter(p => p.verified && p.in_current_raffle);
        
        if (verified.length === 0) {
            verifiedList.innerHTML = '<p class="no-verified">No verified participants yet</p>';
            return;
        }
        
        verifiedList.innerHTML = verified.map(p => `
            <div class="verified-item">
                <span class="verified-name">${p.name}</span>
                <span class="verified-phone">${p.phone}</span>
                <span class="verified-wager">$${p.wager}</span>
                <span class="verified-entries">${p.wager / 10} entries</span>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading participants:', error);
    }
}

// Verify participant
async function verifyParticipant(id) {
    try {
        const response = await fetch(`/api/admin/participants/${id}/verify`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert(data.message);
            loadPendingParticipants();
            loadAllParticipants();
            loadRaffleStatus();
        } else {
            alert(data.error || 'Error verifying participant');
        }
    } catch (error) {
        console.error('Error verifying participant:', error);
        alert('Error verifying participant');
    }
}

// Reject participant
async function rejectParticipant(id) {
    if (!confirm('Are you sure you want to reject this entry?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/participants/${id}/reject`, {
            method: 'POST'
        });
        
        if (response.ok) {
            loadPendingParticipants();
        } else {
            alert('Error rejecting participant');
        }
    } catch (error) {
        console.error('Error rejecting participant:', error);
        alert('Error rejecting participant');
    }
}

// Trigger draw
async function triggerDraw() {
    if (!confirm('Are you sure you want to trigger a draw now?')) {
        return;
    }
    
    try {
        triggerDrawBtn.disabled = true;
        triggerDrawBtn.textContent = 'Drawing...';
        
        const response = await fetch('/api/raffle/draw', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            if (data.winners && data.winners.length > 0) {
                alert(`Draw complete!\n\nWinners:\n${data.winners.map(w => 
                    `${w.position}. ${w.name}: +$${w.amount}`
                ).join('\n')}`);
            } else {
                alert('Draw complete! No participants in this raffle.');
            }
            loadRaffleStatus();
            loadPendingParticipants();
            loadAllParticipants();
        } else {
            alert(data.error || 'Error triggering draw');
        }
    } catch (error) {
        console.error('Error triggering draw:', error);
        alert('Error triggering draw');
    } finally {
        triggerDrawBtn.disabled = false;
        triggerDrawBtn.textContent = '🎲 Trigger Draw Now';
    }
}

// Reset system
async function resetSystem() {
    if (!confirm('WARNING: This will delete ALL participants and raffle history.\n\nAre you absolutely sure?')) {
        return;
    }
    
    if (!confirm('This cannot be undone. Click OK to confirm.')) {
        return;
    }
    
    try {
        resetSystemBtn.disabled = true;
        
        const response = await fetch('/api/admin/reset', {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('System has been reset.');
            loadRaffleStatus();
            loadPendingParticipants();
            loadAllParticipants();
        } else {
            alert('Error resetting system');
        }
    } catch (error) {
        console.error('Error resetting system:', error);
        alert('Error resetting system');
    } finally {
        resetSystemBtn.disabled = false;
    }
}

// Helpers
function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString();
}

// Make functions globally available
window.verifyParticipant = verifyParticipant;
window.rejectParticipant = rejectParticipant;
