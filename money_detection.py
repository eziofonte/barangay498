import os
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
from ultralytics import YOLO

# ── YOLOv8 Model ─────────────────────────────────────────────────────────────
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runs', 'detect', 'peso_bills_clean', 'weights', 'best.pt')
model = YOLO(MODEL_PATH)

YOLO_CONFIDENCE = 0.35

# ── HSV Color Detection Constants ─────────────────────────────────────────────
MIN_BILL_AREA      = 0.012
MIN_FILL_RATIO     = 0.35
ASPECT_MIN         = 1.4
ASPECT_MAX         = 6.0
SINGLE_BILL_ASPECT = 2.4
OVERLAP_IOU        = 0.20


def _clean(mask):
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (14, 14))
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)


def _bill_count_and_contours(mask, total_pixels):
    contours, _ = cv2.findContours(_clean(mask), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = total_pixels * MIN_BILL_AREA
    count = 0
    valid = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        _, (rw, rh), _ = cv2.minAreaRect(c)
        if min(rw, rh) == 0:
            continue
        aspect = max(rw, rh) / min(rw, rh)
        fill   = area / (rw * rh)
        if not (ASPECT_MIN <= aspect <= ASPECT_MAX):
            continue
        if fill < MIN_FILL_RATIO:
            continue
        n = max(1, round(aspect / SINGLE_BILL_ASPECT))
        count += n
        valid.append(c)
    return count, valid


def _iou(c1, c2):
    x1, y1, w1, h1 = cv2.boundingRect(c1)
    x2, y2, w2, h2 = cv2.boundingRect(c2)
    ix = max(0, min(x1+w1, x2+w2) - max(x1, x2))
    iy = max(0, min(y1+h1, y2+h2) - max(y1, y2))
    inter = ix * iy
    union = w1*h1 + w2*h2 - inter
    return inter / union if union > 0 else 0


def _recount(contours):
    total = 0
    for c in contours:
        _, (rw, rh), _ = cv2.minAreaRect(c)
        if min(rw, rh) == 0:
            continue
        total += max(1, round(max(rw, rh) / min(rw, rh) / SINGLE_BILL_ASPECT))
    return total


def _yolo_detect(img_array):
    results = model(img_array, conf=YOLO_CONFIDENCE, verbose=False)
    counts = {'1000peso': 0, '500peso': 0}
    for result in results:
        for box in result.boxes:
            label = model.names[int(box.cls)]
            if label in counts:
                counts[label] += 1
    return counts['500peso'], counts['1000peso']


def _color_detect(img_array):
    hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
    total_pixels = img_array.shape[0] * img_array.shape[1]

    yellow_mask = cv2.inRange(hsv, np.array([12, 45, 50]), np.array([48, 255, 255]))
    blue_mask   = cv2.inRange(hsv, np.array([95, 45, 45]), np.array([135, 255, 255]))

    yellow_count, yellow_contours = _bill_count_and_contours(yellow_mask, total_pixels)
    _, blue_contours_raw = _bill_count_and_contours(blue_mask, total_pixels)
    blue_contours = [
        bc for bc in blue_contours_raw
        if not any(_iou(bc, yc) > OVERLAP_IOU for yc in yellow_contours)
    ]
    blue_count = _recount(blue_contours)
    return yellow_count, blue_count


def detect_money(image_bytes):
    try:
        pil_image = Image.open(BytesIO(image_bytes)).convert('RGB')
        img_array = np.array(pil_image)

        # Try YOLO first
        yellow_count, blue_count = _yolo_detect(img_array)

        # If YOLO found nothing, fall back to color detection
        if yellow_count == 0 and blue_count == 0:
            print("YOLO found nothing — falling back to color detection")
            yellow_count, blue_count = _color_detect(img_array)

        total = (yellow_count * 500) + (blue_count * 1000)

        return {
            'detected':     total == 1500,
            'total':        total,
            'yellow_count': yellow_count,
            'blue_count':   blue_count,
        }

    except Exception as e:
        print(f"Money detection error: {e}")
        return {'detected': False, 'total': 0, 'yellow_count': 0, 'blue_count': 0}