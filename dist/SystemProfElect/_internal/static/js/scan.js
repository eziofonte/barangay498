// Scan Page — Webcam, Face Recognition, Blink Detection, Signature, Release Photo, Auto-clear

// --- Blink Detection State ---
let blinkDetected = false;
let blinkCheckInterval = null;
let autoClearTimer = null;
let countdownInterval = null;
let pendingMatchData = null;
let releaseStream = null;
let isDrawing = false;
let signatureCtx = null;

// --- Blink Detection ---
function startBlinkDetection() {
    const status = document.getElementById('blinkStatus');
    const scanBtn = document.getElementById('scanBtn');

    blinkDetected = false;
    scanBtn.disabled = true;
    status.style.display = 'block';
    status.textContent = '👁 Please blink to verify you are present...';
    status.className = 'blink-status blink-waiting';

    if (blinkCheckInterval) clearInterval(blinkCheckInterval);

    // Reset server-side counter
    fetch('/detect-blink', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reset: true })
    });

    blinkCheckInterval = setInterval(async () => {
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        const imageData = canvas.toDataURL('image/jpeg');

        try {
            const response = await fetch('/detect-blink', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageData })
            });
            const data = await response.json();

            if (!data.face) {
                status.textContent = '⚠ No face detected. Please position yourself in front of the camera.';
                status.className = 'blink-status blink-warning';
            } else if (data.blink) {
                clearInterval(blinkCheckInterval);
                blinkDetected = true;
                status.textContent = '✓ Blink detected! You may now scan.';
                status.className = 'blink-status blink-success';
                scanBtn.disabled = false;
            } else {
                status.textContent = '👁 Please blink to verify you are present...';
                status.className = 'blink-status blink-waiting';
            }
        } catch (err) {
            console.error('Blink detection error:', err);
        }
    }, 500);
}

// --- Camera Init ---
document.addEventListener('DOMContentLoaded', function () {
    const video = document.getElementById('video');
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            video.srcObject = stream;
            video.onloadedmetadata = () => {
                startBlinkDetection();
            };
        })
        .catch(() => { alert('Camera access denied. Please allow camera access.'); });
});

// --- Scan Face ---
async function scanFace() {
    const btn = document.getElementById('scanBtn');
    const loading = document.getElementById('loading');
    const resultBox = document.getElementById('result');

    const canvas = document.getElementById('canvas');
    const video = document.getElementById('video');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const imageData = canvas.toDataURL('image/jpeg');

    btn.disabled = true;
    loading.style.display = 'flex';
    resultBox.style.display = 'none';

    try {
        const response = await fetch('/recognize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: imageData })
        });
        const data = await response.json();

        loading.style.display = 'none';
        btn.disabled = false;

        if (data.status === 'match') {
            pendingMatchData = data;
            showConfirmation(data);
        } else {
            resultBox.style.display = 'block';
            if (data.status === 'already_claimed') {
                resultBox.className = 'result result-already';
                resultBox.innerHTML = `<p class="error-msg">Already Claimed — ${data.message}</p>`;
            } else if (data.status === 'no_match') {
                resultBox.className = 'result result-nomatch';
                resultBox.innerHTML = `<p class="error-msg">No Match — ${data.message}</p>`;
            } else {
                resultBox.className = 'result result-noface';
                resultBox.innerHTML = `<p class="warning-msg">No Face Detected — ${data.message}</p>`;
            }
            startAutoClear(resultBox);
            startBlinkDetection();
        }
    } catch (err) {
        loading.style.display = 'none';
        btn.disabled = false;
        resultBox.style.display = 'block';
        resultBox.className = 'result result-nomatch';
        resultBox.innerHTML = `<p class="error-msg">Something went wrong. Please try again.</p>`;
        startAutoClear(resultBox);
        startBlinkDetection();
    }
}

// --- Show Confirmation ---
function showConfirmation(data) {
    const overlay = document.getElementById('confirmationOverlay');
    document.getElementById('confirmPhoto').src = '/' + data.photo;
    document.getElementById('confirmName').textContent = data.name;
    document.getElementById('confirmAge').textContent = 'Age: ' + data.age;
    document.getElementById('confirmAddress').textContent = data.address;
    document.getElementById('confirmRef').textContent = 'Ref: ' + data.reference_number;
    overlay.classList.add('visible');

    initSignaturePad();
    startReleaseCamera();
}

// --- Release Camera ---
function startReleaseCamera() {
    const video = document.getElementById('releaseVideo');
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            releaseStream = stream;
            video.srcObject = stream;
        })
        .catch(() => { alert('Camera access needed for release photo.'); });
}

function captureReleasePhoto() {
    const video = document.getElementById('releaseVideo');
    const canvas = document.getElementById('releaseCanvas');
    const captured = document.getElementById('releaseCaptured');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const imageData = canvas.toDataURL('image/jpeg');
    captured.src = imageData;
    captured.style.display = 'block';
    video.style.display = 'none';
    document.getElementById('captureReleaseBtn').style.display = 'none';
    document.getElementById('retakeReleaseBtn').style.display = 'inline-block';
    if (releaseStream) releaseStream.getTracks().forEach(t => t.stop());
}

function retakeReleasePhoto() {
    document.getElementById('releaseCaptured').style.display = 'none';
    document.getElementById('releaseVideo').style.display = 'block';
    document.getElementById('captureReleaseBtn').style.display = 'inline-block';
    document.getElementById('retakeReleaseBtn').style.display = 'none';
    startReleaseCamera();
}

// --- Signature Pad ---
function initSignaturePad() {
    const canvas = document.getElementById('signatureCanvas');
    signatureCtx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth;
    canvas.height = 150;
    signatureCtx.strokeStyle = '#1a365d';
    signatureCtx.lineWidth = 2.5;
    signatureCtx.lineCap = 'round';

    canvas.addEventListener('mousedown', startDraw);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', stopDraw);
    canvas.addEventListener('mouseleave', stopDraw);
    canvas.addEventListener('touchstart', e => { e.preventDefault(); startDraw(e.touches[0]); });
    canvas.addEventListener('touchmove', e => { e.preventDefault(); draw(e.touches[0]); });
    canvas.addEventListener('touchend', stopDraw);
}

function startDraw(e) {
    isDrawing = true;
    const rect = document.getElementById('signatureCanvas').getBoundingClientRect();
    signatureCtx.beginPath();
    signatureCtx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
}

function draw(e) {
    if (!isDrawing) return;
    const rect = document.getElementById('signatureCanvas').getBoundingClientRect();
    signatureCtx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
    signatureCtx.stroke();
}

function stopDraw() { isDrawing = false; }

function clearSignature() {
    const canvas = document.getElementById('signatureCanvas');
    signatureCtx.clearRect(0, 0, canvas.width, canvas.height);
}

// --- Confirm Release ---
async function confirmRelease() {
    const signatureCanvas = document.getElementById('signatureCanvas');
    const releaseCaptured = document.getElementById('releaseCaptured');

    const signatureData = signatureCanvas.toDataURL('image/png');
    const releasePhotoData = releaseCaptured.src || null;

    try {
        const response = await fetch('/confirm-release', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                transaction_id: pendingMatchData.transaction_id,
                signature: signatureData,
                release_photo: releasePhotoData
            })
        });
        const data = await response.json();

        const overlay = document.getElementById('confirmationOverlay');
        overlay.classList.remove('visible');

        const resultBox = document.getElementById('result');
        resultBox.style.display = 'block';
        resultBox.className = 'result result-match';
        resultBox.innerHTML = `
            <div class="result-inner">
                <img src="/${pendingMatchData.photo}" alt="${pendingMatchData.name}" />
                <div class="result-info">
                    <h3>Match Found — ${pendingMatchData.name}</h3>
                    <p>Age: ${pendingMatchData.age}</p>
                    <p>${pendingMatchData.address}</p>
                    <p style="font-size:13px;color:#718096;margin-top:4px;">Ref: ${data.reference_number}</p>
                    <span class="release-tag">Money Released — ₱1,500.00</span>
                </div>
            </div>`;

        startAutoClear(resultBox);
        startBlinkDetection();
    } catch (err) {
        alert('Something went wrong confirming the release. Please try again.');
    }
}

function cancelRelease() {
    const overlay = document.getElementById('confirmationOverlay');
    overlay.classList.remove('visible');
    if (releaseStream) releaseStream.getTracks().forEach(t => t.stop());
    pendingMatchData = null;
    startBlinkDetection();
}

// --- Auto Clear ---
function startAutoClear(resultBox) {
    if (autoClearTimer) clearTimeout(autoClearTimer);
    if (countdownInterval) clearInterval(countdownInterval);

    let seconds = 10;
    const countdown = document.getElementById('autoClearCountdown');
    if (countdown) {
        countdown.textContent = `Result will clear in ${seconds} seconds`;
        countdownInterval = setInterval(() => {
            seconds--;
            if (seconds > 0) {
                countdown.textContent = `Result will clear in ${seconds} seconds`;
            } else {
                clearInterval(countdownInterval);
                countdown.textContent = '';
            }
        }, 1000);
    }

    autoClearTimer = setTimeout(() => {
        resultBox.style.display = 'none';
        resultBox.innerHTML = '';
    }, 10000);
}