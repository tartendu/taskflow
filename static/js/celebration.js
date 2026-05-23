// Party Popper Celebration Animation

function celebrate() {
    // Create confetti container
    const confettiContainer = document.createElement('div');
    confettiContainer.className = 'confetti-container';
    confettiContainer.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 9999;
        overflow: hidden;
    `;
    document.body.appendChild(confettiContainer);

    // Confetti colors
    const colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe', '#43e97b', '#38f9d7', '#fa709a', '#fee140'];

    // Create multiple confetti pieces
    const confettiCount = 150;
    for (let i = 0; i < confettiCount; i++) {
        setTimeout(() => {
            createConfetti(confettiContainer, colors);
        }, i * 10);
    }

    // Remove container after animation
    setTimeout(() => {
        confettiContainer.remove();
    }, 5000);
}

function createConfetti(container, colors) {
    const confetti = document.createElement('div');
    const color = colors[Math.floor(Math.random() * colors.length)];
    const size = Math.random() * 10 + 5;
    const left = Math.random() * 100;
    const animationDuration = Math.random() * 3 + 2;
    const rotation = Math.random() * 360;
    const delay = Math.random() * 0.5;

    confetti.style.cssText = `
        position: absolute;
        width: ${size}px;
        height: ${size}px;
        background-color: ${color};
        top: -20px;
        left: ${left}%;
        opacity: 1;
        transform: rotate(${rotation}deg);
        animation: confettiFall ${animationDuration}s ease-out ${delay}s forwards;
    `;

    // Random shape
    if (Math.random() > 0.5) {
        confetti.style.borderRadius = '50%';
    }

    container.appendChild(confetti);

    // Remove after animation
    setTimeout(() => {
        confetti.remove();
    }, (animationDuration + delay) * 1000);
}

// Add CSS animations
const celebrationStyle = document.createElement('style');
celebrationStyle.textContent = `
    @keyframes confettiFall {
        0% {
            transform: translateY(0) rotate(0deg);
            opacity: 1;
        }
        100% {
            transform: translateY(100vh) rotate(720deg);
            opacity: 0;
        }
    }

    @keyframes celebrationPop {
        0% {
            transform: translate(-50%, -50%) scale(0);
            opacity: 0;
        }
        50% {
            transform: translate(-50%, -50%) scale(1.1);
        }
        100% {
            transform: translate(-50%, -50%) scale(1);
            opacity: 1;
        }
    }

    @keyframes celebrationFadeOut {
        to {
            transform: translate(-50%, -50%) scale(0.8);
            opacity: 0;
        }
    }

    .celebration-content {
        background: white;
        padding: 3rem 4rem;
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        text-align: center;
    }

    .celebration-icon {
        font-size: 5rem;
        margin-bottom: 1rem;
        animation: bounce 0.5s ease infinite alternate;
    }

    @keyframes bounce {
        from { transform: translateY(0); }
        to { transform: translateY(-10px); }
    }

    .celebration-content h2 {
        font-size: 2rem;
        color: #2c3e50;
        margin-bottom: 0.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .celebration-content p {
        font-size: 1.1rem;
        color: #7f8c8d;
    }
`;
document.head.appendChild(celebrationStyle);

// Make celebrate function globally available
window.celebrate = celebrate;
