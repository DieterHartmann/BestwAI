/**
 * BestwAI Raffle - User Signup Page JavaScript
 */

// State
let wagerAmount = 10;
let raffleData = null;

// DOM Elements
const signupForm = document.getElementById('signupForm');
const nameInput = document.getElementById('nameInput');
const phoneInput = document.getElementById('phoneInput');
const pinInput = document.getElementById('pinInput');
const wagerValue = document.getElementById('wagerValue');
const entryCount = document.getElementById('entryCount');
const decreaseWager = document.getElementById('decreaseWager');
const increaseWager = document.getElementById('increaseWager');
const submitBtn = document.getElementById('submitBtn');
const submitAmount = document.getElementById('submitAmount');
const formFeedback = document.getElementById('formFeedback');
const signupSection = document.getElementById('signupSection');
const successSection = document.getElementById('successSection');
const successMessage = document.getElementById('successMessage');
const paymentAmount = document.getElementById('paymentAmount');
const countdown = document.getElementById('countdown');
const potSize = document.getElementById('potSize');
const participantCount = document.getElementById('participantCount');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Set up event listeners
    decreaseWager.addEventListener('click', () => updateWager(-10));
    increaseWager.addEventListener('click', () => updateWager(10));
    signupForm.addEventListener('submit', handleSignup);
    
    // Start polling for raffle updates
    updateRaffleInfo();
    setInterval(updateRaffleInfo, 3000);
    setInterval(updateCountdown, 1000);
});

// Update wager amount
function updateWager(delta) {
    wagerAmount = Math.max(10, wagerAmount + delta);
    wagerValue.textContent = wagerAmount;
    submitAmount.textContent = wagerAmount;
    entryCount.textContent = wagerAmount / 10;
}

// Handle signup form submission
async function handleSignup(e) {
    e.preventDefault();
    
    const name = nameInput.value.trim();
    const phone = phoneInput.value.trim();
    const pin = pinInput.value.trim();
    
    if (!name) {
        showFeedback('Please enter your name', 'error');
        return;
    }
    
    if (!phone) {
        showFeedback('Please enter your phone number', 'error');
        return;
    }
    
    if (!pin) {
        showFeedback('Admin PIN required. Hand phone to admin.', 'error');
        return;
    }
    
    // Disable form
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';
    
    try {
        const response = await fetch('/api/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                phone: phone,
                wager: wagerAmount,
                pin: pin
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            showFeedback(data.error || 'Failed to register', 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = `Submit Entry - $${wagerAmount}`;
            return;
        }
        
        // Show success
        showSuccess(data.message);
        
    } catch (error) {
        console.error('Error submitting signup:', error);
        showFeedback('Connection error. Please try again.', 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = `Submit Entry - $${wagerAmount}`;
    }
}

// Show success section
function showSuccess(message) {
    signupSection.classList.add('hidden');
    successSection.classList.remove('hidden');
    successMessage.textContent = message;
    paymentAmount.textContent = wagerAmount;
}

// Update raffle information
async function updateRaffleInfo() {
    try {
        const response = await fetch('/api/raffle/current');
        raffleData = await response.json();
        
        potSize.textContent = '$' + raffleData.total_pot;
        participantCount.textContent = raffleData.participant_count;
        
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

// Helper: Pad numbers
function pad(num) {
    return String(num).padStart(2, '0');
}

// Helper: Show feedback message
function showFeedback(message, type) {
    formFeedback.textContent = message;
    formFeedback.className = `form-feedback ${type}`;
    formFeedback.classList.remove('hidden');
    
    setTimeout(() => {
        formFeedback.classList.add('hidden');
    }, 5000);
}
