/**
 * BestwAI Raffle - Display Screen JavaScript
 */

// State
let raffleData = null;
let lastRaffleId = null;
let isDrawing = false;

// DOM Elements
const countdownTimer = document.getElementById('countdownTimer');
const statusIndicator = document.getElementById('statusIndicator');
const displayPot = document.getElementById('displayPot');
const displayParticipants = document.getElementById('displayParticipants');
const participantsGrid = document.getElementById('participantsGrid');
const historyList = document.getElementById('historyList');
const drawOverlay = document.getElementById('drawOverlay');
const spinningNames = document.getElementById('spinningNames');
const winnersReveal = document.getElementById('winnersReveal');
const winnerList = document.getElementById('winnerList');
const confettiCanvas = document.getElementById('confettiCanvas');
const telegramMessages = document.getElementById('telegramMessages');
const telegramQr = document.getElementById('telegramQr');
const telegramBotName = document.getElementById('telegramBotName');
const telegramCard = document.getElementById('telegramCard');

// Confetti setup
const ctx = confettiCanvas.getContext('2d');
let confettiPieces = [];

function resizeCanvas() {
    confettiCanvas.width = window.innerWidth;
    confettiCanvas.height = window.innerHeight;
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    updateRaffleInfo();
    loadHistory();
    loadTelegramBotInfo();
    loadTelegramMessages();
    setInterval(updateRaffleInfo, 2000);
    setInterval(updateCountdown, 1000);
    setInterval(checkForNewDraw, 3000);
    setInterval(loadTelegramMessages, 3000);
});

// Update raffle information
async function updateRaffleInfo() {
    try {
        const response = await fetch('/api/raffle/current');
        raffleData = await response.json();
        
        // Update display
        displayPot.textContent = raffleData.total_pot.toLocaleString();
        displayParticipants.textContent = raffleData.participant_count;
        
        // Update status
        updateStatus(raffleData.status);
        
        // Update participants grid
        updateParticipantsGrid(raffleData.participants);
        
        // Check if draw is happening
        if (raffleData.status === 'drawing' && !isDrawing) {
            startDrawAnimation();
        }
        
    } catch (error) {
        console.error('Error updating raffle info:', error);
    }
}

// Update countdown timer
function updateCountdown() {
    if (!raffleData || !raffleData.draw_time) {
        countdownTimer.textContent = '--:--:--';
        return;
    }
    
    const drawTime = new Date(raffleData.draw_time);
    const now = new Date();
    const diff = drawTime - now;
    
    if (diff <= 0) {
        countdownTimer.textContent = '00:00:00';
        countdownTimer.style.color = '#f59e0b';
        return;
    }
    
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);
    
    countdownTimer.textContent = `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
    countdownTimer.style.color = diff < 60000 ? '#ef4444' : '#3b82f6';
}

// Update status indicator
function updateStatus(status) {
    const statusText = statusIndicator.querySelector('.status-text');
    
    if (status === 'drawing') {
        statusIndicator.classList.add('drawing');
        statusText.textContent = 'Drawing Winners...';
    } else {
        statusIndicator.classList.remove('drawing');
        statusText.textContent = 'Accepting Entries';
    }
}

// Update participants grid
function updateParticipantsGrid(participants) {
    if (!participants || participants.length === 0) {
        participantsGrid.innerHTML = '<p class="no-participants">Scan QR code to join!</p>';
        return;
    }
    
    participantsGrid.innerHTML = participants.map(p => `
        <div class="participant-tag">
            <span class="participant-name">${p.name}</span>
            <span class="participant-entries">${p.entries}x</span>
            <span class="participant-wager">$${p.wager}</span>
        </div>
    `).join('');
}

// Check for new draw completion
async function checkForNewDraw() {
    try {
        const response = await fetch('/api/raffle/latest-winners');
        const data = await response.json();
        
        if (data.raffle_id && data.raffle_id !== lastRaffleId && data.winners.length > 0) {
            lastRaffleId = data.raffle_id;
            
            if (!isDrawing) {
                showWinnersAnimation(data.winners, data.total_pot);
            }
            
            loadHistory();
        }
    } catch (error) {
        console.error('Error checking for new draw:', error);
    }
}

// Load raffle history
async function loadHistory() {
    try {
        const response = await fetch('/api/raffle/history?limit=5');
        const history = await response.json();
        
        if (!history || history.length === 0) {
            historyList.innerHTML = '<p class="no-history">No draws yet</p>';
            return;
        }
        
        historyList.innerHTML = history.map(raffle => `
            <div class="history-item">
                <div class="history-time">${formatTime(raffle.draw_time)}</div>
                <div class="history-pot">💰 $${raffle.total_pot}</div>
                <div class="history-winners">
                    ${raffle.winners.map(w => `
                        <div class="history-winner">
                            <span class="position">${getPositionEmoji(w.position)}</span>
                            <span class="name">${w.name}</span>
                            <span class="amount">+$${w.amount}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// Start draw animation
async function startDrawAnimation() {
    isDrawing = true;
    drawOverlay.classList.remove('hidden');
    winnersReveal.classList.add('hidden');
    spinningNames.classList.remove('hidden');
    
    const participants = raffleData.participants || [];
    if (participants.length === 0) {
        endDrawAnimation();
        return;
    }
    
    // Spin through names
    const spinElement = spinningNames.querySelector('.spin-name');
    let spinCount = 0;
    const maxSpins = 30;
    
    const spinInterval = setInterval(() => {
        const randomParticipant = participants[Math.floor(Math.random() * participants.length)];
        spinElement.textContent = randomParticipant.name;
        spinCount++;
        
        if (spinCount >= maxSpins) {
            clearInterval(spinInterval);
            setTimeout(fetchAndShowWinners, 1000);
        }
    }, 100 + (spinCount * 10));
}

// Fetch winners and show reveal
async function fetchAndShowWinners() {
    try {
        const response = await fetch('/api/raffle/latest-winners');
        const data = await response.json();
        
        if (data.winners && data.winners.length > 0) {
            showWinnersAnimation(data.winners, data.total_pot);
        } else {
            setTimeout(fetchAndShowWinners, 1000);
        }
    } catch (error) {
        console.error('Error fetching winners:', error);
        endDrawAnimation();
    }
}

// Show winners animation
function showWinnersAnimation(winners, totalPot) {
    isDrawing = true;
    drawOverlay.classList.remove('hidden');
    spinningNames.classList.add('hidden');
    winnersReveal.classList.remove('hidden');
    winnerList.innerHTML = '';
    
    // Reveal winners one by one
    winners.forEach((winner, index) => {
        setTimeout(() => {
            const winnerEl = document.createElement('div');
            winnerEl.className = `reveal-winner place-${winner.position}`;
            winnerEl.innerHTML = `
                <span class="position">${getPositionEmoji(winner.position)}</span>
                <span class="name">${winner.name}</span>
                <span class="amount">+$${winner.amount}</span>
            `;
            winnerList.appendChild(winnerEl);
            
            if (index === 0) {
                startConfetti();
            }
            
            if (index === winners.length - 1) {
                setTimeout(() => {
                    endDrawAnimation();
                    loadHistory();
                }, 5000);
            }
        }, (index + 1) * 800);
    });
}

// End draw animation
function endDrawAnimation() {
    isDrawing = false;
    drawOverlay.classList.add('hidden');
    stopConfetti();
    updateRaffleInfo();
}

// Confetti animation
function startConfetti() {
    confettiPieces = [];
    const colors = ['#fbbf24', '#f59e0b', '#22c55e', '#3b82f6', '#ef4444', '#a855f7'];
    
    for (let i = 0; i < 200; i++) {
        confettiPieces.push({
            x: Math.random() * confettiCanvas.width,
            y: -20,
            size: Math.random() * 10 + 5,
            color: colors[Math.floor(Math.random() * colors.length)],
            speedY: Math.random() * 3 + 2,
            speedX: (Math.random() - 0.5) * 4,
            rotation: Math.random() * 360,
            rotationSpeed: (Math.random() - 0.5) * 10
        });
    }
    
    animateConfetti();
}

function animateConfetti() {
    if (confettiPieces.length === 0) return;
    
    ctx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
    
    confettiPieces.forEach((piece, index) => {
        piece.y += piece.speedY;
        piece.x += piece.speedX;
        piece.rotation += piece.rotationSpeed;
        
        ctx.save();
        ctx.translate(piece.x, piece.y);
        ctx.rotate((piece.rotation * Math.PI) / 180);
        ctx.fillStyle = piece.color;
        ctx.fillRect(-piece.size / 2, -piece.size / 2, piece.size, piece.size);
        ctx.restore();
        
        if (piece.y > confettiCanvas.height + 20) {
            confettiPieces.splice(index, 1);
        }
    });
    
    if (confettiPieces.length > 0) {
        requestAnimationFrame(animateConfetti);
    }
}

function stopConfetti() {
    confettiPieces = [];
    ctx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
}

// Helpers
function pad(num) {
    return String(num).padStart(2, '0');
}

function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function getPositionEmoji(position) {
    const emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'];
    return emojis[position - 1] || `${position}`;
}

// =============================================================================
// Telegram Integration
// =============================================================================
async function loadTelegramBotInfo() {
    try {
        const response = await fetch('/api/telegram/bot-info');
        if (response.ok) {
            const data = await response.json();
            if (data.qr_code) {
                if (telegramQr) {
                    telegramQr.innerHTML = `<img src="data:image/png;base64,${data.qr_code}" alt="Telegram Bot QR">`;
                }
                if (telegramBotName) {
                    telegramBotName.textContent = `@${data.bot_username}`;
                }
                if (telegramCard) {
                    telegramCard.style.display = 'block';
                }
            }
        } else {
            // Hide telegram card if bot not configured
            if (telegramCard) telegramCard.style.display = 'none';
        }
    } catch (error) {
        console.log('Telegram bot not configured:', error);
        if (telegramCard) telegramCard.style.display = 'none';
    }
}

async function loadTelegramMessages() {
    try {
        const response = await fetch('/api/telegram/messages?limit=5');
        if (response.ok) {
            const messages = await response.json();
            updateTelegramDisplay(messages);
        }
    } catch (error) {
        console.error('Error loading Telegram messages:', error);
    }
}

function updateTelegramDisplay(messages) {
    if (!telegramMessages) return;
    
    if (messages.length === 0) {
        telegramMessages.innerHTML = '<p class="no-messages">Send a message via Telegram!</p>';
        return;
    }
    
    telegramMessages.innerHTML = messages.map(msg => `
        <div class="telegram-msg">
            <span class="msg-user">@${msg.username || 'user'}:</span>
            <span class="msg-text">${escapeHtml(msg.message)}</span>
        </div>
    `).join('');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
