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
    startReleaseCamera();
    showFixedSignature("Senior's Signature", 'regular');
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

    const signatureData = getFixedSignatureData();
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
        hideFixedSignature();

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
    document.getElementById('confirmationOverlay').classList.remove('visible');
    hideFixedSignature();
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

// --- Proxy Release ---
async function openProxyModal() {
    // Load seniors list
    const response = await fetch('/seniors-list');
    const data = await response.json();
    const select = document.getElementById('proxySeniorSelect');
    select.innerHTML = '<option value="">-- Select Senior --</option>';
    window._seniorsList = data.seniors;
    data.seniors.forEach(s => {
        select.innerHTML += `<option value="${s.id}">${s.name} (Age: ${s.age})</option>`;
    });
    document.getElementById('proxyModal').classList.add('visible');
    document.getElementById('proxyError').style.display = 'none';
    document.getElementById('captainPin').value = '';
    document.getElementById('proxyName').value = '';
    document.getElementById('proxyRelationship').value = '';
}

function closeProxyModal() {
    document.getElementById('proxyModal').classList.remove('visible');
}

async function submitProxyRelease() {
    const senior_id = document.getElementById('proxySeniorSelect').value;
    const proxy_name = document.getElementById('proxyName').value.trim();
    const proxy_relationship = document.getElementById('proxyRelationship').value.trim();
    const captain_pin = document.getElementById('captainPin').value;
    const errorBox = document.getElementById('proxyError');

    if (!senior_id || !proxy_name || !proxy_relationship || !captain_pin) {
        errorBox.textContent = 'Please fill in all fields.';
        errorBox.style.display = 'block';
        return;
    }

    // Verify PIN first before showing confirmation
    try {
        const verifyResponse = await fetch('/verify-captain-pin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ captain_pin })
        });
        const verifyData = await verifyResponse.json();
        if (verifyData.status !== 'ok') {
            errorBox.textContent = verifyData.message;
            errorBox.style.display = 'block';
            return;
        }
    } catch (err) {
        errorBox.textContent = 'Something went wrong. Please try again.';
        errorBox.style.display = 'block';
        return;
    }

    // PIN verified — close proxy modal and show proxy confirmation
    closeProxyModal();
    openProxyConfirmation(senior_id, proxy_name, proxy_relationship, captain_pin);
}

function openProxyConfirmation(senior_id, proxy_name, proxy_relationship, captain_pin) {
    // Store proxy details for later
    window._proxyData = { senior_id, proxy_name, proxy_relationship, captain_pin };

    // Reset confirmation fields
    document.getElementById('proxyConfirmPhoto').src = '';
    document.getElementById('proxyPhotoData').value = '';
    window._proxySignatureData = null;

    // Show the senior name
    const select = document.getElementById('proxySeniorSelect');
    const seniorName = select.options[select.selectedIndex]?.text || '';
    const selectedSenior = window._seniorsList.find(s => s.id == senior_id);
    document.getElementById('proxyConfirmSeniorName').textContent = selectedSenior ? selectedSenior.name : seniorName.split(' (')[0];
    document.getElementById('proxyConfirmSeniorAge').textContent = selectedSenior ? 'Age: ' + selectedSenior.age : '';
    document.getElementById('proxyConfirmSeniorAddress').textContent = selectedSenior ? selectedSenior.address : '';
    document.getElementById('proxyConfirmSeniorPhoto').src = selectedSenior && selectedSenior.photo ? '/' + selectedSenior.photo.replace(/^\//, '') : '';
    document.getElementById('proxyConfirmProxyName').textContent = proxy_name;

    // Mirror main webcam stream into proxy video
    // Start mirroring main video to proxy canvas
    const mainVideo = document.getElementById('video');
    const proxyCanvas = document.getElementById('proxyVideoCanvas');
    proxyCanvas.width = mainVideo.videoWidth;
    proxyCanvas.height = mainVideo.videoHeight;
    proxyCanvas.style.display = 'block';
    document.getElementById('proxyConfirmPhoto').style.display = 'none';
    document.getElementById('proxyPhotoData').value = '';

    window._proxyMirrorInterval = setInterval(() => {
        if (mainVideo.readyState >= 2) {
            proxyCanvas.getContext('2d').drawImage(mainVideo, 0, 0, proxyCanvas.width, proxyCanvas.height);
        }
    }, 50);

    document.getElementById('proxyConfirmModal').classList.add('visible');
    showFixedSignature("Proxy's Signature", 'proxy');
}

function closeProxyConfirmation() {
    clearInterval(window._proxyMirrorInterval);
    document.getElementById('proxyConfirmModal').classList.remove('visible');
    hideFixedSignature();
}

// --- Proxy signature pad ---
function startProxySignaturePad() {
    const canvas = document.getElementById('proxySignaturePad');
    const ctx = canvas.getContext('2d');
    let drawing = false;

    canvas.onmousedown = (e) => { drawing = true; ctx.beginPath(); ctx.moveTo(e.offsetX, e.offsetY); };
    canvas.onmousemove = (e) => { if (!drawing) return; ctx.lineWidth = 2; ctx.lineCap = 'round'; ctx.strokeStyle = '#1a365d'; ctx.lineTo(e.offsetX, e.offsetY); ctx.stroke(); };
    canvas.onmouseup = () => { drawing = false; window._proxySignatureData = canvas.toDataURL('image/png'); };
    canvas.onmouseleave = () => { drawing = false; };

    // Touch support
    canvas.ontouchstart = (e) => { e.preventDefault(); drawing = true; const t = e.touches[0]; const r = canvas.getBoundingClientRect(); ctx.beginPath(); ctx.moveTo(t.clientX - r.left, t.clientY - r.top); };
    canvas.ontouchmove = (e) => { e.preventDefault(); if (!drawing) return; const t = e.touches[0]; const r = canvas.getBoundingClientRect(); ctx.lineWidth = 2; ctx.lineCap = 'round'; ctx.strokeStyle = '#1a365d'; ctx.lineTo(t.clientX - r.left, t.clientY - r.top); ctx.stroke(); };
    canvas.ontouchend = () => { drawing = false; window._proxySignatureData = canvas.toDataURL('image/png'); };
}

function clearProxySignature() {
    const canvas = document.getElementById('proxySignaturePad');
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    window._proxySignatureData = null;
}

// --- Proxy live photo ---
function takeProxyPhoto() {
    clearInterval(window._proxyMirrorInterval);
    const mainVideo = document.getElementById('video');
    const canvas = document.createElement('canvas');
    canvas.width = mainVideo.videoWidth;
    canvas.height = mainVideo.videoHeight;
    canvas.getContext('2d').drawImage(mainVideo, 0, 0);
    const photoData = canvas.toDataURL('image/jpeg');

    document.getElementById('proxyVideoCanvas').style.display = 'none';
    document.getElementById('proxyConfirmPhoto').style.display = 'block';
    document.getElementById('proxyConfirmPhoto').src = photoData;
    document.getElementById('proxyPhotoData').value = photoData;

    document.getElementById('proxyConfirmError').style.display = 'none';
}

// --- Final proxy submission ---
async function confirmProxyRelease() {
    const errorBox = document.getElementById('proxyConfirmError');
    const photoData = document.getElementById('proxyPhotoData').value;
    const signatureData = getFixedSignatureData();

    if (!photoData) {
        errorBox.textContent = 'Please take a live photo first.';
        errorBox.style.display = 'block';
        return;
    }
    if (!signatureData) {
        errorBox.textContent = 'Please get the proxy\'s signature first.';
        errorBox.style.display = 'block';
        return;
    }

    const { senior_id, proxy_name, proxy_relationship, captain_pin } = window._proxyData;

    try {
        const response = await fetch('/proxy-release', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                senior_id, proxy_name, proxy_relationship, captain_pin,
                release_photo: photoData,
                signature: signatureData
            })
        });
        const data = await response.json();

        if (data.status === 'success') {
            closeProxyConfirmation();
            hideFixedSignature();
            const resultBox = document.getElementById('result');
            resultBox.style.display = 'block';
            resultBox.className = 'result result-match';
            resultBox.innerHTML = `
                <div class="result-info">
                    <h3>Proxy Release Authorized</h3>
                    <p><strong>Senior:</strong> ${data.senior_name}</p>
                    <p><strong>Proxy:</strong> ${data.proxy_name}</p>
                    <p style="font-size:13px;color:#718096;margin-top:4px;">Ref: ${data.reference_number}</p>
                    <span class="release-tag">₱1,500.00 Released via Proxy</span>
                </div>`;
            startAutoClear(resultBox);
            startBlinkDetection();
        } else {
            errorBox.textContent = data.message;
            errorBox.style.display = 'block';
        }
    } catch (err) {
        errorBox.textContent = 'Something went wrong. Please try again.';
        errorBox.style.display = 'block';
    }
}

// --- Fixed Signature Pad ---
let fixedSignatureCtx = null;
let fixedSignatureDrawing = false;

function initFixedSignaturePad() {
    const canvas = document.getElementById('fixedSignatureCanvas');
    fixedSignatureCtx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth;
    canvas.height = 150;
    fixedSignatureCtx.strokeStyle = '#1a365d';
    fixedSignatureCtx.lineWidth = 2.5;
    fixedSignatureCtx.lineCap = 'round';

    // Pointer events — works for mouse, stylus pen, and touch
    canvas.onpointerdown = (e) => {
        canvas.setPointerCapture(e.pointerId);
        fixedSignatureDrawing = true;
        fixedSignatureCtx.beginPath();
        fixedSignatureCtx.moveTo(e.offsetX, e.offsetY);
    };
    canvas.onpointermove = (e) => {
        if (!fixedSignatureDrawing) return;
        fixedSignatureCtx.lineTo(e.offsetX, e.offsetY);
        fixedSignatureCtx.stroke();
    };
    canvas.onpointerup = () => { fixedSignatureDrawing = false; };
    canvas.onpointercancel = () => { fixedSignatureDrawing = false; };
}

function showFixedSignature(label, mode) {
    const overlay = document.getElementById('fixedSignatureOverlay');
    document.getElementById('fixedSignatureLabel').textContent = label;
    const actions = document.getElementById('fixedSignatureActions');

    if (mode === 'regular') {
        actions.innerHTML = `
            <button class="btn btn-outline" onclick="cancelRelease()">Cancel</button>
            <button class="btn btn-confirm" onclick="confirmRelease()">Confirm Release</button>
        `;
    } else {
        actions.innerHTML = `
            <button class="btn btn-outline" onclick="closeProxyConfirmation()">Cancel</button>
            <button class="btn btn-confirm" onclick="confirmProxyRelease()">Confirm Release</button>
        `;
    }

    overlay.classList.add('visible');
    clearFixedSignature();
    initFixedSignaturePad();
}

function hideFixedSignature() {
    document.getElementById('fixedSignatureOverlay').classList.remove('visible');
}

function clearFixedSignature() {
    const canvas = document.getElementById('fixedSignatureCanvas');
    if (fixedSignatureCtx) fixedSignatureCtx.clearRect(0, 0, canvas.width, canvas.height);
}

function getFixedSignatureData() {
    return document.getElementById('fixedSignatureCanvas').toDataURL('image/png');
}