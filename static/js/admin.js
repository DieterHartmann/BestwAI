/**
 * BestwAI Raffle - Admin Panel JavaScript
 */

// DOM Elements
const triggerDrawBtn = document.getElementById('triggerDrawBtn');
const resetSystemBtn = document.getElementById('resetSystemBtn');
const generateTokensBtn = document.getElementById('generateTokensBtn');
const refreshTokensBtn = document.getElementById('refreshTokensBtn');
const saveConfigBtn = document.getElementById('saveConfigBtn');
const printTokensBtn = document.getElementById('printTokensBtn');

const tokenCountInput = document.getElementById('tokenCount');
const tokenBalanceInput = document.getElementById('tokenBalance');
const configEntryCost = document.getElementById('configEntryCost');
const configDrawInterval = document.getElementById('configDrawInterval');
const configStartingBalance = document.getElementById('configStartingBalance');

const raffleStatus = document.getElementById('raffleStatus');
const rafflePot = document.getElementById('rafflePot');
const raffleParticipants = document.getElementById('raffleParticipants');
const raffleDrawTime = document.getElementById('raffleDrawTime');

const generatedTokensSection = document.getElementById('generatedTokens');
const tokenCards = document.getElementById('tokenCards');
const tokensTableBody = document.getElementById('tokensTableBody');
const printContent = document.getElementById('printContent');

// State
let generatedTokensList = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    loadRaffleStatus();
    loadTokens();
    
    // Set up event listeners
    triggerDrawBtn.addEventListener('click', triggerDraw);
    resetSystemBtn.addEventListener('click', resetSystem);
    generateTokensBtn.addEventListener('click', generateTokens);
    refreshTokensBtn.addEventListener('click', loadTokens);
    saveConfigBtn.addEventListener('click', saveConfig);
    printTokensBtn.addEventListener('click', printTokens);
    
    // Auto-refresh status
    setInterval(loadRaffleStatus, 5000);
});

// Load configuration
async function loadConfig() {
    try {
        const response = await fetch('/api/admin/config');
        const config = await response.json();
        
        configEntryCost.value = config.entry_cost;
        configDrawInterval.value = config.draw_interval;
        configStartingBalance.value = config.starting_balance;
        tokenBalanceInput.value = config.starting_balance;
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
                entry_cost: parseInt(configEntryCost.value),
                draw_interval: parseInt(configDrawInterval.value),
                starting_balance: parseInt(configStartingBalance.value)
            })
        });
        
        if (response.ok) {
            alert('Configuration saved successfully!');
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
        rafflePot.textContent = `${data.total_pot} tokens`;
        raffleParticipants.textContent = data.participant_count;
        
        const drawTime = new Date(data.draw_time);
        raffleDrawTime.textContent = drawTime.toLocaleString();
    } catch (error) {
        console.error('Error loading raffle status:', error);
    }
}

// Trigger draw manually
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
                    `${w.position}. ${w.token_id}: +${w.amount} tokens`
                ).join('\n')}`);
            } else {
                alert('Draw complete! No participants in this raffle.');
            }
            loadRaffleStatus();
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
    if (!confirm('WARNING: This will delete ALL tokens, entries, and raffle history.\n\nAre you absolutely sure?')) {
        return;
    }
    
    if (!confirm('This action cannot be undone. Type "RESET" mentally and click OK to confirm.')) {
        return;
    }
    
    try {
        resetSystemBtn.disabled = true;
        
        const response = await fetch('/api/admin/reset', {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('System has been reset successfully.');
            loadRaffleStatus();
            loadTokens();
            generatedTokensSection.classList.add('hidden');
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

// Generate tokens
async function generateTokens() {
    const count = parseInt(tokenCountInput.value) || 10;
    const balance = parseInt(tokenBalanceInput.value) || 100;
    
    try {
        generateTokensBtn.disabled = true;
        generateTokensBtn.textContent = 'Generating...';
        
        const response = await fetch('/api/admin/tokens/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ count, balance })
        });
        
        generatedTokensList = await response.json();
        
        // Display generated tokens
        tokenCards.innerHTML = generatedTokensList.map(token => `
            <div class="token-card">
                <div class="token-card-title">BestwAI Raffle Token</div>
                <div class="token-card-id">${token.token_id}</div>
                <div class="token-card-qr">
                    <img src="data:image/png;base64,${token.qr_code}" alt="QR Code">
                </div>
                <div class="token-card-balance">Starting Balance: <span>${token.balance}</span> tokens</div>
            </div>
        `).join('');
        
        generatedTokensSection.classList.remove('hidden');
        loadTokens();
        
    } catch (error) {
        console.error('Error generating tokens:', error);
        alert('Error generating tokens');
    } finally {
        generateTokensBtn.disabled = false;
        generateTokensBtn.textContent = 'Generate Tokens';
    }
}

// Load all tokens
async function loadTokens() {
    try {
        const response = await fetch('/api/admin/tokens');
        const tokens = await response.json();
        
        if (tokens.length === 0) {
            tokensTableBody.innerHTML = '<tr><td colspan="4">No tokens generated yet</td></tr>';
            return;
        }
        
        tokensTableBody.innerHTML = tokens.map(token => `
            <tr>
                <td class="token-id">${token.token_id}</td>
                <td class="balance">${token.balance}</td>
                <td>${formatDate(token.created_at)}</td>
                <td class="actions">
                    <button class="btn btn-secondary btn-sm" onclick="editBalance('${token.token_id}', ${token.balance})">
                        Edit
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading tokens:', error);
        tokensTableBody.innerHTML = '<tr><td colspan="4">Error loading tokens</td></tr>';
    }
}

// Edit token balance
async function editBalance(tokenId, currentBalance) {
    const newBalance = prompt(`Enter new balance for ${tokenId}:`, currentBalance);
    
    if (newBalance === null) return;
    
    const balance = parseInt(newBalance);
    if (isNaN(balance) || balance < 0) {
        alert('Please enter a valid positive number');
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/tokens/${tokenId}/balance`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ balance })
        });
        
        if (response.ok) {
            loadTokens();
        } else {
            alert('Error updating balance');
        }
    } catch (error) {
        console.error('Error updating balance:', error);
        alert('Error updating balance');
    }
}

// Print tokens
function printTokens() {
    if (generatedTokensList.length === 0) {
        alert('No tokens to print. Generate tokens first.');
        return;
    }
    
    printContent.innerHTML = `
        <style>
            .print-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; padding: 20px; }
            .print-card { border: 2px solid #000; padding: 20px; text-align: center; page-break-inside: avoid; }
            .print-title { font-size: 14px; color: #666; margin-bottom: 10px; }
            .print-id { font-size: 24px; font-family: monospace; font-weight: bold; margin-bottom: 15px; }
            .print-qr img { max-width: 150px; }
            .print-balance { font-size: 12px; color: #666; margin-top: 10px; }
            @media print { body { -webkit-print-color-adjust: exact; } }
        </style>
        <div class="print-grid">
            ${generatedTokensList.map(token => `
                <div class="print-card">
                    <div class="print-title">BestwAI Raffle Token</div>
                    <div class="print-id">${token.token_id}</div>
                    <div class="print-qr">
                        <img src="data:image/png;base64,${token.qr_code}" alt="QR">
                    </div>
                    <div class="print-balance">Starting Balance: ${token.balance} tokens</div>
                </div>
            `).join('')}
        </div>
    `;
    
    window.print();
}

// Helper: Format date
function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString();
}

// Make editBalance available globally
window.editBalance = editBalance;
