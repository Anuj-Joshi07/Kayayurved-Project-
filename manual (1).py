import cv2
import json
import os

PAGES = {
    "page7": "manual_pages/page_8.png",
    "page11": "manual_pages/page_12.png"
}

CONFIG_FILE = "layout_config.json"
config = {}

for key, img_path in PAGES.items():
    img = cv2.imread(img_path)
    clone = img.copy()

    state = {
        "drawing": False,
        "ix": -1,
        "iy": -1,
        "rois": []
    }

    def draw(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            state["drawing"] = True
            state["ix"], state["iy"] = x, y

        elif event == cv2.EVENT_LBUTTONUP:
            state["drawing"] = False
            x1, y1 = state["ix"], state["iy"]
            state["rois"].append((x1, y1, x, y))
            cv2.rectangle(img, (x1, y1), (x, y), (0, 255, 0), 2)
            cv2.imshow(key, img)

    cv2.namedWindow(key)
    cv2.setMouseCallback(key, draw)

    print(f"""
{key.upper()} SELECTION MODE
--------------------------------
1️⃣ Draw BAR first
2️⃣ Draw each ROW (top → bottom)
3️⃣ Press 's' to save
4️⃣ Press 'r' to reset
""")

    while True:
        cv2.imshow(key, img)
        k = cv2.waitKey(1) & 0xFF

        if k == ord('s'):
            break
        elif k == ord('r'):
            img = clone.copy()
            state["rois"] = []

    cv2.destroyAllWindows()

    config[key] = {
        "bar": state["rois"][0],
        "rows": state["rois"][1:]
    }

with open(CONFIG_FILE, "w") as f:
    json.dump(config, f, indent=4)

print("✅ layout_config.json saved successfully")
