// Scan Page — Webcam and Face Recognition
document.addEventListener('DOMContentLoaded', function () {
    const video = document.getElementById('video');

    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => { video.srcObject = stream; })
        .catch(() => { alert('Camera access denied. Please allow camera access.'); });
});

async function scanFace() {
    const btn = document.getElementById('scanBtn');
    const loading = document.getElementById('loading');
    const resultBox = document.getElementById('result');
    const resultContent = document.getElementById('result-content');

    const canvas = document.getElementById('canvas');
    const video = document.getElementById('video');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const imageData = canvas.toDataURL('image/jpeg');

    btn.disabled = true;
    loading.style.display = 'block';
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
        resultBox.style.display = 'block';

        if (data.status === 'match') {
            resultBox.className = 'result result-match';
            resultContent.innerHTML = `
                <div class="result-inner">
                    <img src="/${data.photo}" alt="${data.name}" />
                    <div class="result-info">
                        <h3>Match Found — ${data.name}</h3>
                        <p>Age: ${data.age}</p>
                        <p>${data.address}</p>
                        <span class="release-tag">Money Released — ₱1,500.00</span>
                    </div>
                </div>`;
        } else if (data.status === 'no_match') {
            resultBox.className = 'result result-nomatch';
            resultContent.innerHTML = `<p class="error-msg">No Match — ${data.message}</p>`;

        } else if (data.status === 'already_claimed') {
    resultBox.className = 'result result-noface';
    resultContent.innerHTML = `<p class="warning-msg">Already Claimed — ${data.message}</p>`;

        } else {
            resultBox.className = 'result result-noface';
            resultContent.innerHTML = `<p class="warning-msg">No Face Detected — ${data.message}</p>`;
        }
    } catch (err) {
        loading.style.display = 'none';
        btn.disabled = false;
        resultBox.style.display = 'block';
        resultBox.className = 'result result-nomatch';
        resultContent.innerHTML = `<p class="error-msg">Something went wrong. Please try again.</p>`;
    }
}