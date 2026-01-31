/**
 * BestwAI Raffle - User Page JavaScript
 */

// State
let currentToken = null;
let entryCost = 10;
let entryCount = 1;
let raffleData = null;

// DOM Elements
const tokenInput = document.getElementById('tokenInput');
const checkTokenBtn = document.getElementById('checkTokenBtn');
const tokenInputSection = document.getElementById('tokenInputSection');
const tokenInfoSection = document.getElementById('tokenInfoSection');
const displayTokenId = document.getElementById('displayTokenId');
const balanceValue = document.getElementById('balanceValue');
const totalWins = document.getElementById('totalWins');
const totalWinnings = document.getElementById('totalWinnings');
const currentEntries = document.getElementById('currentEntries');
const entryCostEl = document.getElementById('entryCost');
const entryCountEl = document.getElementById('entryCount');
const totalCostEl = document.getElementById('totalCost');
const decreaseBtn = document.getElementById('decreaseEntries');
const increaseBtn = document.getElementById('increaseEntries');
const enterRaffleBtn = document.getElementById('enterRaffleBtn');
const entryFeedback = document.getElementById('entryFeedback');
const countdown = document.getElementById('countdown');
const potSize = document.getElementById('potSize');
const participantCount = document.getElementById('participantCount');
const recentWinners = document.getElementById('recentWinners');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check if token ID was passed in URL
    if (tokenInput.value) {
        checkToken();
    }
    
    // Set up event listeners
    checkTokenBtn.addEventListener('click', checkToken);
    tokenInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') checkToken();
    });
    
    decreaseBtn.addEventListener('click', () => updateEntryCount(-1));
    increaseBtn.addEventListener('click', () => updateEntryCount(1));
    enterRaffleBtn.addEventListener('click', enterRaffle);
    
    // Start polling for updates
    updateRaffleInfo();
    loadRecentWinners();
    setInterval(updateRaffleInfo, 3000);
    setInterval(updateCountdown, 1000);
});

// Check token and load balance
async function checkToken() {
    const tokenId = tokenInput.value.trim().toUpperCase();
    if (!tokenId) {
        showFeedback('Please enter a token ID', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/token/${tokenId}`);
        if (!response.ok) {
            if (response.status === 404) {
                showFeedback('Token not found. Please check your token ID.', 'error');
            } else {
                showFeedback('Error checking token. Please try again.', 'error');
            }
            return;
        }
        
        currentToken = await response.json();
        displayTokenInfo();
    } catch (error) {
        console.error('Error checking token:', error);
        showFeedback('Connection error. Please try again.', 'error');
    }
}

// Display token information
function displayTokenInfo() {
    if (!currentToken) return;
    
    displayTokenId.textContent = currentToken.token_id;
    balanceValue.textContent = currentToken.balance;
    totalWins.textContent = currentToken.total_wins;
    totalWinnings.textContent = currentToken.total_winnings;
    currentEntries.textContent = currentToken.current_entries;
    
    tokenInfoSection.classList.remove('hidden');
    
    // Update entry cost display
    if (raffleData) {
        entryCostEl.textContent = raffleData.entry_cost;
        entryCost = raffleData.entry_cost;
    }
    updateTotalCost();
}

// Update entry count
function updateEntryCount(delta) {
    entryCount = Math.max(1, entryCount + delta);
    entryCountEl.textContent = entryCount;
    updateTotalCost();
}

// Update total cost display
function updateTotalCost() {
    const total = entryCount * entryCost;
    totalCostEl.textContent = total;
    
    // Disable button if insufficient balance
    if (currentToken && total > currentToken.balance) {
        enterRaffleBtn.disabled = true;
        enterRaffleBtn.textContent = 'Insufficient Balance';
    } else {
        enterRaffleBtn.disabled = false;
        enterRaffleBtn.textContent = 'Enter Raffle';
    }
}

// Enter raffle
async function enterRaffle() {
    if (!currentToken) {
        showFeedback('Please check your token first', 'error');
        return;
    }
    
    const total = entryCount * entryCost;
    if (total > currentToken.balance) {
        showFeedback('Insufficient balance', 'error');
        return;
    }
    
    enterRaffleBtn.disabled = true;
    enterRaffleBtn.textContent = 'Entering...';
    
    try {
        const response = await fetch('/api/raffle/enter', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                token_id: currentToken.token_id,
                entries: entryCount
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            showFeedback(data.error || 'Failed to enter raffle', 'error');
            return;
        }
        
        // Update local state
        currentToken.balance = data.new_balance;
        currentToken.current_entries = data.total_entries;
        displayTokenInfo();
        
        showFeedback(`Successfully entered with ${entryCount} entry(s)!`, 'success');
        
        // Reset entry count
        entryCount = 1;
        entryCountEl.textContent = 1;
        updateTotalCost();
        
        // Update raffle info
        updateRaffleInfo();
        
    } catch (error) {
        console.error('Error entering raffle:', error);
        showFeedback('Connection error. Please try again.', 'error');
    } finally {
        enterRaffleBtn.disabled = false;
        enterRaffleBtn.textContent = 'Enter Raffle';
        updateTotalCost();
    }
}

// Update raffle information
async function updateRaffleInfo() {
    try {
        const response = await fetch('/api/raffle/current');
        raffleData = await response.json();
        
        potSize.textContent = raffleData.total_pot;
        participantCount.textContent = raffleData.participant_count;
        entryCost = raffleData.entry_cost;
        entryCostEl.textContent = entryCost;
        
        updateTotalCost();
        
        // Refresh token info if we have a token
        if (currentToken) {
            const tokenResponse = await fetch(`/api/token/${currentToken.token_id}`);
            if (tokenResponse.ok) {
                currentToken = await tokenResponse.json();
                displayTokenInfo();
            }
        }
    } catch (error) {
        console.error('Error updating raffle info:', error);
    }
}

// Update countdown timer
function updateCountdown() {
    if (!raffleData || !raffleData.draw_time) {
        countdown.textContent = '--:--:--';
        return;
    }
    
    const drawTime = new Date(raffleData.draw_time);
    const now = new Date();
    const diff = drawTime - now;
    
    if (diff <= 0) {
        countdown.textContent = 'DRAWING...';
        return;
    }
    
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);
    
    countdown.textContent = `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

// Load recent winners
async function loadRecentWinners() {
    try {
        const response = await fetch('/api/raffle/history?limit=3');
        const history = await response.json();
        
        if (!history || history.length === 0) {
            recentWinners.innerHTML = '<p class="no-winners">No winners yet</p>';
            return;
        }
        
        recentWinners.innerHTML = history.map(raffle => `
            <div class="winner-draw">
                <div class="draw-info">Pot: ${raffle.total_pot} tokens</div>
                ${raffle.winners.map(w => `
                    <div class="winner-item">
                        <span class="winner-position">${getPositionEmoji(w.position)}</span>
                        <span class="winner-token">${w.token_id}</span>
                        <span class="winner-amount">+${w.amount}</span>
                    </div>
                `).join('')}
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading winners:', error);
    }
}

// Helper: Pad numbers
function pad(num) {
    return String(num).padStart(2, '0');
}

// Helper: Get position emoji
function getPositionEmoji(position) {
    const emojis = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'];
    return emojis[position - 1] || `${position}`;
}

// Helper: Show feedback message
function showFeedback(message, type) {
    entryFeedback.textContent = message;
    entryFeedback.className = `entry-feedback ${type}`;
    entryFeedback.classList.remove('hidden');
    
    setTimeout(() => {
        entryFeedback.classList.add('hidden');
    }, 5000);
}
