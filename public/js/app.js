/**
 * NetServe Frontend Application Logic
 * Implements interactive canvas particles, network animation, and live status checking.
 */

document.addEventListener('DOMContentLoaded', () => {
    initParticles();
    initServerStatusCheck();
    initInteractiveTester();
});

/**
 * 1. Background Network Particle Canvas Animation
 */
function initParticles() {
    const canvas = document.createElement('canvas');
    canvas.id = 'particles-canvas';
    document.body.prepend(canvas);

    const ctx = canvas.getContext('2d');
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    window.addEventListener('resize', () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    });

    const particles = [];
    const count = Math.min(Math.floor((width * height) / 25000), 50);

    for (let i = 0; i < count; i++) {
        particles.push({
            x: Math.random() * width,
            y: Math.random() * height,
            vx: (Math.random() - 0.5) * 0.6,
            vy: (Math.random() - 0.5) * 0.6,
            radius: Math.random() * 2 + 1,
            color: Math.random() > 0.4 ? 'rgba(56, 189, 248, 0.4)' : 'rgba(16, 185, 129, 0.4)'
        });
    }

    function animate() {
        ctx.clearRect(0, 0, width, height);

        // Draw connections
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 130) {
                    ctx.strokeStyle = `rgba(56, 189, 248, ${0.15 * (1 - dist / 130)})`;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.stroke();
                }
            }
        }

        // Draw particles
        particles.forEach(p => {
            p.x += p.vx;
            p.y += p.vy;

            if (p.x < 0) p.x = width;
            if (p.x > width) p.x = 0;
            if (p.y < 0) p.y = height;
            if (p.y > height) p.y = 0;

            ctx.fillStyle = p.color;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            ctx.fill();
        });

        requestAnimationFrame(animate);
    }

    animate();
}

/**
 * 2. Live Server Status Check
 */
function initServerStatusCheck() {
    const statusBadges = document.querySelectorAll('.server-status-badge');
    
    async function checkStatus() {
        try {
            const start = performance.now();
            const res = await fetch('/api/status');
            const data = await res.json();
            const latency = Math.round(performance.now() - start);

            statusBadges.forEach(badge => {
                badge.innerHTML = `<span class="status-dot"></span> Online (${data.uptime} • ${latency}ms)`;
                badge.style.color = 'var(--accent-emerald)';
            });
        } catch (e) {
            statusBadges.forEach(badge => {
                badge.innerHTML = `<span class="status-dot" style="background: var(--accent-rose)"></span> Offline`;
                badge.style.color = 'var(--accent-rose)';
            });
        }
    }

    if (statusBadges.length > 0) {
        checkStatus();
        setInterval(checkStatus, 5000);
    }
}

/**
 * 3. Interactive Request Simulator for Docs / Home
 */
function initInteractiveTester() {
    const btn = document.getElementById('btnTestRequest');
    const input = document.getElementById('testPathInput');
    const output = document.getElementById('testOutput');

    if (!btn || !input || !output) return;

    btn.addEventListener('click', async () => {
        const path = input.value.trim() || '/api/status';
        output.textContent = `Connecting to NetServe via TCP...\nSending GET ${path} HTTP/1.1\n\nWaiting for response...`;

        const startTime = performance.now();
        try {
            const res = await fetch(path);
            const duration = Math.round(performance.now() - startTime);
            const status = `${res.status} ${res.statusText}`;

            let bodyText = '';
            const contentType = res.headers.get('content-type') || '';

            if (contentType.includes('application/json')) {
                const json = await res.json();
                bodyText = JSON.stringify(json, null, 2);
            } else {
                bodyText = await res.text();
                if (bodyText.length > 500) {
                    bodyText = bodyText.substring(0, 500) + '\n... [truncated]';
                }
            }

            const headerList = [];
            res.headers.forEach((val, key) => {
                headerList.push(`${key}: ${val}`);
            });

            output.textContent = 
`HTTP/1.1 ${status} (${duration}ms)
${headerList.join('\n')}

${bodyText}`;
        } catch (err) {
            output.textContent = `[Network Error]: Unable to reach ${path}\n${err.message}`;
        }
    });
}
