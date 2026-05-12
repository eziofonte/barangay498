from ultralytics import YOLO

if __name__ == '__main__':
    model = YOLO('yolov8n.pt')

    results = model.train(
        data='Peso-Bill-Detection-4/data.yaml',
        epochs=100,
        imgsz=640,
        batch=16,
        device=0,
        workers=0,
        name='peso_bills_v2',
        patience=20
    )

    print("Training complete! Model saved to runs/detect/peso_bills_v2/weights/best.pt")