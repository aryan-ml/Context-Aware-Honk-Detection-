import cv2
import time

URL = "http://10.181.118.4:4747/video"

cap = cv2.VideoCapture(URL)

if not cap.isOpened():
    print("Failed to connect to camera.")
    exit()

prev = time.time()

while True:
    ret, frame = cap.read()

    if not ret:
        print("Failed to read frame.")
        break

    curr = time.time()
    fps = 1 / (curr - prev)
    prev = curr

    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2,
    )

    cv2.imshow("Phone Camera", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()