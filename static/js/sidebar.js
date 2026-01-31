/**
 * BestwAI Raffle - Sidebar Toggle
 */

document.addEventListener('DOMContentLoaded', () => {
    const sidebar = document.getElementById('storySidebar');
    const toggle = document.getElementById('sidebarToggle');
    const overlay = document.getElementById('sidebarOverlay');
    
    if (!sidebar || !toggle || !overlay) return;
    
    // Toggle sidebar
    function toggleSidebar() {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('open');
        
        // Update toggle button text
        if (sidebar.classList.contains('open')) {
            toggle.textContent = '✕';
            toggle.setAttribute('aria-expanded', 'true');
        } else {
            toggle.textContent = '☰';
            toggle.setAttribute('aria-expanded', 'false');
        }
    }
    
    // Close sidebar
    function closeSidebar() {
        sidebar.classList.remove('open');
        overlay.classList.remove('open');
        toggle.textContent = '☰';
        toggle.setAttribute('aria-expanded', 'false');
    }
    
    // Event listeners
    toggle.addEventListener('click', toggleSidebar);
    overlay.addEventListener('click', closeSidebar);
    
    // Close on escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar.classList.contains('open')) {
            closeSidebar();
        }
    });
    
    // Close on window resize if going to desktop
    window.addEventListener('resize', () => {
        if (window.innerWidth > 1024 && sidebar.classList.contains('open')) {
            closeSidebar();
        }
    });
});
