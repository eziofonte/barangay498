// Register & Edit Senior — Photo Preview + Camera Capture

document.addEventListener('DOMContentLoaded', function () {

    // --- Upload mode: file preview ---
    const photoInput = document.getElementById('photo');
    if (photoInput) {
        photoInput.addEventListener('change', function (e) {
            const file = e.target.files[0];
            if (file) {
                // Update upload area text
                const uploadText = document.querySelector('.upload-text');
                const uploadSubtext = document.querySelector('.upload-subtext');
                if (uploadText) uploadText.textContent = file.name;
                if (uploadSubtext) uploadSubtext.textContent = 'Click to change photo';

                const reader = new FileReader();
                reader.onload = function (e) {
                    document.getElementById('preview-img').src = e.target.result;
                    document.getElementById('preview-img').style.display = 'block';
                    document.getElementById('preview-placeholder').style.display = 'none';
                }
                reader.readAsDataURL(file);
            }
        });
    }
});

// --- Toggle between upload and camera modes ---
let cameraStream = null;

function switchMode(mode) {
    const uploadMode = document.getElementById('uploadMode');
    const cameraSection = document.getElementById('cameraSection');
    const btnUpload = document.getElementById('btnUpload');
    const btnCamera = document.getElementById('btnCamera');
    const photoInput = document.getElementById('photo');

    if (mode === 'camera') {
        uploadMode.style.display = 'none';
        cameraSection.classList.add('visible');
        btnUpload.classList.remove('active');
        btnCamera.classList.add('active');
        photoInput.removeAttribute('required');
        startCamera();
    } else {
        cameraSection.classList.remove('visible');
        uploadMode.style.display = 'block';
        btnUpload.classList.add('active');
        btnCamera.classList.remove('active');
        if (!photoInput.dataset.optional) {
            photoInput.setAttribute('required', 'required');
        }
        stopCamera();
    }
}

function startCamera() {
    const video = document.getElementById('regVideo');
    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            cameraStream = stream;
            video.srcObject = stream;
            video.style.display = 'block';
            document.getElementById('capturedPhoto').style.display = 'none';
            document.getElementById('captureBtn').style.display = 'inline-block';
            document.getElementById('retakeBtn').style.display = 'none';
        })
        .catch(() => { alert('Camera access denied. Please allow camera access.'); });
}

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
}

function capturePhoto() {
    const video = document.getElementById('regVideo');
    const canvas = document.getElementById('regCanvas');
    const capturedPhoto = document.getElementById('capturedPhoto');

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);

    const imageData = canvas.toDataURL('image/jpeg');
    document.getElementById('captured_photo').value = imageData;

    // Show captured image, hide video
    capturedPhoto.src = imageData;
    capturedPhoto.style.display = 'block';
    video.style.display = 'none';
    document.getElementById('captureBtn').style.display = 'none';
    document.getElementById('retakeBtn').style.display = 'inline-block';

    stopCamera();
}

function retakePhoto() {
    document.getElementById('captured_photo').value = '';
    document.getElementById('capturedPhoto').style.display = 'none';
    startCamera();
}

// Stop camera if user navigates away
window.addEventListener('beforeunload', stopCamera);

function changeAge(delta) {
    const input = document.getElementById('ageInput');
    const current = parseInt(input.value) || 60;
    const newVal = current + delta;
    if (newVal >= 60 && newVal <= 130) {
        input.value = newVal;
    }
}