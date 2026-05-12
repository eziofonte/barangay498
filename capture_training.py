import cv2
import os
import time

save_folder = input("Folder name (e.g. '1000' or '500'): ").strip()
os.makedirs(f'webcam_training/{save_folder}', exist_ok=True)

cap = cv2.VideoCapture(0)
count = 0

print(f"Starting capture for {save_folder}...")
print("Taking a photo every 2 seconds. Adjust the bill between shots.")
print("Press Ctrl+C to stop.")

try:
    while True:
        ret, frame = cap.read()
        if ret:
            filename = f'webcam_training/{save_folder}/{save_folder}_{count:03d}.jpg'
            cv2.imwrite(filename, frame)
            count += 1
            print(f'Saved {filename}')
        time.sleep(2)
except KeyboardInterrupt:
    pass

cap.release()
print(f'Done! Saved {count} images.')