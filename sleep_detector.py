"""Desktop version of the Sleep Detector - uses MediaPipe Face Mesh + Eye
Aspect Ratio (EAR) instead of Haar Cascades for reliable open/closed eye
detection (see detector_core.py for the same approach used by the web app).
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import os
import threading
from datetime import datetime

try:
    import winsound
    SOUND_AVAILABLE = True
except ImportError:
    SOUND_AVAILABLE = False  # if Windows is not available, sound will be skipped

try:
    import pygame
    pygame.mixer.init()
    PYGAME_MIXER_AVAILABLE = True
except (ImportError, Exception):
    PYGAME_MIXER_AVAILABLE = False

# --- MediaPipe Face Mesh setup ---
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

LEFT_EYE_IDX = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_IDX = [33, 160, 158, 133, 153, 144]

# Tune this after checking printed EAR values if needed (see DEBUG_PRINT_EAR)
EAR_THRESHOLD = 0.21
DEBUG_PRINT_EAR = False

# Settings for sleep detection thresholds
YELLOW_THRESHOLD_FRAMES = 8    # early warning - slightly closed eyes
RED_THRESHOLD_FRAMES = 20      # full alarm - eyes significantly closed
SCREENSHOT_FOLDER = "sleep_detection_screenshots"
ALERT_SOUND_FILE = "sleep-alert.mp3"

closed_counter = 0  # count of consecutive frames with eyes closed
sleep_detection_event_count = 0
was_red_last_frame = False
alert_sound_active = False
_beep_stop_event = threading.Event()
session_start_time = time.time()

os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)


def _euclidean(p1, p2):
    return float(np.linalg.norm(np.array(p1) - np.array(p2)))


def _eye_aspect_ratio(landmarks, eye_idx, w, h):
    pts = [(landmarks[i].x * w, landmarks[i].y * h) for i in eye_idx]
    p1, p2, p3, p4, p5, p6 = pts
    vertical_1 = _euclidean(p2, p6)
    vertical_2 = _euclidean(p3, p5)
    horizontal = _euclidean(p1, p4)
    if horizontal == 0:
        return 0.0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def detect_face_and_eyes(frame_bgr):
    """
    Returns (face_coords, eyes_open, eye_points):
      - face_coords: (x, y, w, h) bounding box of the face, or None
      - eyes_open: bool
      - eye_points: list of (x, y) pixel coords for drawing
    """
    h, w = frame_bgr.shape[:2]
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)

    if not results.multi_face_landmarks:
        return None, False, []

    landmarks = results.multi_face_landmarks[0].landmark

    left_ear = _eye_aspect_ratio(landmarks, LEFT_EYE_IDX, w, h)
    right_ear = _eye_aspect_ratio(landmarks, RIGHT_EYE_IDX, w, h)
    avg_ear = (left_ear + right_ear) / 2.0

    if DEBUG_PRINT_EAR:
        print(f"[EAR] left={left_ear:.3f} right={right_ear:.3f} avg={avg_ear:.3f} threshold={EAR_THRESHOLD}")

    eyes_open = avg_ear > EAR_THRESHOLD

    xs = [lm.x * w for lm in landmarks]
    ys = [lm.y * h for lm in landmarks]
    face_coords = (
        int(min(xs)),
        int(min(ys)),
        int(max(xs) - min(xs)),
        int(max(ys) - min(ys)),
    )

    eye_points = [
        (int(landmarks[i].x * w), int(landmarks[i].y * h))
        for i in LEFT_EYE_IDX + RIGHT_EYE_IDX
    ]

    return face_coords, eyes_open, eye_points


def _beep_loop():
    """Fallback: repeat beep until stop is requested."""
    while not _beep_stop_event.is_set():
        if SOUND_AVAILABLE:
            winsound.Beep(1200, 400)
        _beep_stop_event.wait(0.5)


def start_alert_sound():
    """Start looping alert sound while eyes stay closed."""
    global alert_sound_active
    if alert_sound_active:
        return
    alert_sound_active = True

    if PYGAME_MIXER_AVAILABLE and os.path.isfile(ALERT_SOUND_FILE):
        try:
            pygame.mixer.music.load(ALERT_SOUND_FILE)
            pygame.mixer.music.play(-1)  # loop until stopped
            return
        except pygame.error as exc:
            print(f"Could not play {ALERT_SOUND_FILE}: {exc}")

    _beep_stop_event.clear()
    threading.Thread(target=_beep_loop, daemon=True).start()


def stop_alert_sound():
    """Stop alert sound when eyes open again."""
    global alert_sound_active
    if not alert_sound_active:
        return
    alert_sound_active = False

    if PYGAME_MIXER_AVAILABLE:
        pygame.mixer.music.stop()
    _beep_stop_event.set()


def save_screenshot(frame):
    """Save frame with timestamp when RED alert event occurs"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(SCREENSHOT_FOLDER, f"sleep_detection_{timestamp}.jpg")
    cv2.imwrite(filepath, frame)
    print(f"Screenshot saved: {filepath}")


def draw_annotations(frame, face_coords, eyes_open, eye_points, alert_level):
    h, w = frame.shape[:2]
    output = frame.copy()

    eye_color = (0, 255, 0) if eyes_open else (0, 0, 255)
    for (px, py) in eye_points:
        cv2.circle(output, (px, py), 2, eye_color, -1)

    if alert_level == "red":
        red_overlay = np.zeros_like(output)
        red_overlay[:] = (0, 0, 255)
        output = cv2.addWeighted(output, 0.75, red_overlay, 0.25, 0)

        pulse = (np.sin(time.time() * 6) + 1) / 2
        border_thickness = int(8 + pulse * 14)
        intensity = int(150 + pulse * 105)
        border_color = (0, 0, intensity)

        status_text = "Sleep ALERT! WAKE UP!"
        text_color = (0, 0, 255)

    elif alert_level == "yellow":
        border_thickness = 10
        border_color = (0, 200, 255)   # amber/yellow (BGR)
        status_text = "Early Warning - Stay Alert"
        text_color = (0, 200, 255)

    else:  # green
        border_thickness = 12
        border_color = (0, 255, 0)
        status_text = "Alert - Eyes Open" if eyes_open else "Watching..."
        text_color = (0, 255, 0)

    cv2.rectangle(output, (0, 0), (w - 1, h - 1), border_color, border_thickness)

    (text_w, text_h), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
    text_x = (w - text_w) // 2
    text_y = 50

    cv2.rectangle(
        output, (text_x - 15, text_y - text_h - 15),
        (text_x + text_w + 15, text_y + 10), (0, 0, 0), -1
    )
    cv2.putText(
        output, status_text, (text_x, text_y),
        cv2.FONT_HERSHEY_SIMPLEX, 0.9, text_color, 2
    )

    elapsed = int(time.time() - session_start_time)
    mins, secs = divmod(elapsed, 60)
    stats_text = f"Time: {mins:02d}:{secs:02d}  |  sleep events: {sleep_detection_event_count}"
    cv2.putText(
        output, stats_text, (20, h - 20),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA
    )

    return output


def print_session_summary():
    elapsed = int(time.time() - session_start_time)
    mins, secs = divmod(elapsed, 60)
    print("\n" + "=" * 40)
    print("SESSION SUMMARY")
    print("=" * 40)
    print(f"Total monitoring time : {mins:02d}:{secs:02d}")
    print(f"Sleep events detected: {sleep_detection_event_count}")
    print(f"Screenshots saved in  : ./{SCREENSHOT_FOLDER}/")
    print("=" * 40)


def main():
    global closed_counter, sleep_detection_event_count, was_red_last_frame

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Webcam failed To open!")
        return

    print("Operating Sleep Detector\n Press q To exit")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame read failed, exiting...")
            break

        face_coords, eyes_open, eye_points = detect_face_and_eyes(frame)

        if not eyes_open:
            closed_counter += 1
        else:
            closed_counter = 0  # eyes clearly open -> reset

        print(f"Face detected: {face_coords is not None} | Eyes open: {eyes_open} | Closed counter: {closed_counter}", end="\r")

        # Multi-level decision logic
        is_red = closed_counter >= RED_THRESHOLD_FRAMES
        is_yellow = (not is_red) and (closed_counter >= YELLOW_THRESHOLD_FRAMES)

        if is_red:
            alert_level = "red"
        elif is_yellow:
            alert_level = "yellow"
        else:
            alert_level = "green"

        # RED alert: loop sound until eyes open; screenshot only on first frame
        if is_red:
            start_alert_sound()
            if not was_red_last_frame:
                sleep_detection_event_count += 1
                save_screenshot(frame)
        else:
            stop_alert_sound()

        was_red_last_frame = is_red

        annotated_frame = draw_annotations(frame, face_coords, eyes_open, eye_points, alert_level)
        cv2.imshow("Sleep Detector", annotated_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    stop_alert_sound()
    print_session_summary()


if __name__ == "__main__":
    main()