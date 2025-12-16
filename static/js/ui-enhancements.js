// UI Enhancement Script for StoryCanvas
// Handles toggle interactions, scene counting, and modern UI effects

// ========== AUTO-GENERATE TOGGLE ========== 
const autoGenToggle = document.getElementById('auto-gen-toggle');
const autoGenTrack = document.getElementById('auto-gen-track');
const autoGenThumb = document.getElementById('auto-gen-thumb');

if (autoGenToggle) {
        autoGenToggle.addEventListener('change', function() {
                if (this.checked) {
                        autoGenThumb.style.left = '24px';
                        autoGenTrack.style.background = 'linear-gradient(90deg, rgba(0,255,136,0.2), rgba(0,217,163,0.15))';
                        autoGenTrack.style.borderColor = 'rgba(0,255,136,0.3)';
                } else {
                        autoGenThumb.style.left = '4px';
                        autoGenTrack.style.background = 'rgba(255,255,255,0.05)';
                        autoGenTrack.style.borderColor = 'rgba(255,255,255,0.06)';
                }
        });
}

// ========== SCENE COUNT UPDATER ==========
function updateSceneCount() {
        const sceneCount = document.getElementById('scene-count');
        const imageContainer = document.getElementById('image-container');
        if (sceneCount && imageContainer) {
                const count = imageContainer.children.length;
                sceneCount.textContent = `${count} scene${count !== 1 ? 's' : ''}`;
        }
}

// Observe scene additions/removals
const imageContainer = document.getElementById('image-container');
if (imageContainer) {
        const observer = new MutationObserver(updateSceneCount);
        observer.observe(imageContainer, { childList: true });
        updateSceneCount(); // Initial count
}

// ========== SMOOTH SCROLLING ==========
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                        target.scrollIntoView({
                                behavior: 'smooth',
                                block: 'start'
                        });
                }
        });
});

// ========== ANIMATED BUTTON RIPPLES ==========
document.querySelectorAll('.terminal-button, .terminal-button-secondary').forEach(button => {
        button.addEventListener('click', function(e) {
                const ripple = document.createElement('span');
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;
                
                ripple.style.width = ripple.style.height = size + 'px';
                ripple.style.left = x + 'px';
                ripple.style.top = y + 'px';
                ripple.classList.add('ripple-effect');
                
                this.appendChild(ripple);
                
                setTimeout(() => ripple.remove(), 600);
        });
});

// ========== INPUT ANIMATION ON FOCUS ==========
document.querySelectorAll('.terminal-input, .terminal-select, textarea.terminal-input').forEach(input => {
        input.addEventListener('focus', function() {
                this.parentElement?.classList.add('input-focused');
        });
        
        input.addEventListener('blur', function() {
                this.parentElement?.classList.remove('input-focused');
        });
});

// ========== CARD ENTRANCE ANIMATIONS ==========
const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
};

const cardObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                        setTimeout(() => {
                                entry.target.style.opacity = '1';
                                entry.target.style.transform = 'translateY(0)';
                        }, index * 100);
                        cardObserver.unobserve(entry.target);
                }
        });
}, observerOptions);

// Apply to scene cards
document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.scene-card').forEach(card => {
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                card.style.transition = 'opacity 0.5s, transform 0.5s';
                cardObserver.observe(card);
        });
});

// ========== TYPING INDICATOR FOR TEXT AREAS ==========
let typingTimer;
document.querySelectorAll('textarea.terminal-input').forEach(textarea => {
        textarea.addEventListener('keyup', function() {
                clearTimeout(typingTimer);
                this.style.borderColor = 'rgba(0,255,136,0.6)';
                
                typingTimer = setTimeout(() => {
                        this.style.borderColor = '';
                }, 1000);
        });
});

// ========== PROGRESS BAR ANIMATION ==========
function animateProgressBar(element, duration = 2000) {
        if (!element) return;
        
        element.style.width = '0%';
        element.style.transition = `width ${duration}ms ease-out`;
        
        setTimeout(() => {
                element.style.width = '100%';
        }, 10);
}

// ========== CONSOLE STYLING (FOR DEBUG) ==========
console.log('%c🎨 StoryCanvas UI Enhanced', 'color: #00ff88; font-size: 16px; font-weight: bold; text-shadow: 0 0 10px #00ff88;');
console.log('%c✨ Modern UI/UX features loaded', 'color: #ff6b9d; font-size: 12px;');
console.log('%c🚀 JetBrains Mono font active', 'color: #ffc266; font-size: 12px;');

