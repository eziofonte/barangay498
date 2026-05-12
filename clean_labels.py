import os

# Old indices: 3=1000peso, 4=500peso
# New indices: 0=1000peso, 1=500peso
KEEP = {3: 0, 4: 1}

def clean_folder(folder):
    label_dir = os.path.join(folder, 'labels')
    if not os.path.exists(label_dir):
        print(f"Skipping {label_dir} — not found")
        return
    
    cleaned = 0
    for filename in os.listdir(label_dir):
        if not filename.endswith('.txt'):
            continue
        filepath = os.path.join(label_dir, filename)
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            parts = line.strip().split()
            if not parts:
                continue
            class_id = int(parts[0])
            if class_id in KEEP:
                parts[0] = str(KEEP[class_id])
                new_lines.append(' '.join(parts) + '\n')
        
        with open(filepath, 'w') as f:
            f.writelines(new_lines)
        cleaned += 1
    
    print(f"✅ Cleaned {cleaned} label files in {label_dir}")

clean_folder('Peso-Bill-Detection-3/train')
clean_folder('Peso-Bill-Detection-3/valid')
clean_folder('Peso-Bill-Detection-3/test')
print("Done!")