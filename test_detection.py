from ultralytics import YOLO
import os

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'runs', 'detect', 'peso_bills_clean', 'weights', 'best.pt')
model = YOLO(MODEL_PATH)

# Test on an image file — put a test photo in your project folder and change the filename
results = model('test_bill.jpg', conf=0.3, verbose=True)

for result in results:
    print("Detections:")
    for box in result.boxes:
        label = model.names[int(box.cls)]
        conf = float(box.conf)
        print(f"  {label}: {conf:.2%} confidence")
    
    if not result.boxes:
        print("  Nothing detected")
    
    result.show()  # opens a window showing the detection boxes