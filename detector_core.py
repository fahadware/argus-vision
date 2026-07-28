"""Shared sleep/drowsiness detection logic for desktop and web apps.

Uses MediaPipe Face Mesh + Eye Aspect Ratio (EAR) instead of Haar Cascades.
This is far more reliable for telling open vs. closed eyes apart, since it
measures actual eye geometry rather than pattern-matching an "eye region"
(which is why the old Haar approach kept firing on closed eyelids).
"""

import os
import time
from datetime import datetime

import cv2
import mediapipe as mp
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

YELLOW_THRESHOLD_FRAMES = 8
RED_THRESHOLD_FRAMES = 20
SCREENSHOT_FOLDER = os.path.join(BASE_DIR, "ARGUS_screenshots")
ALERT_SOUND_FILE = os.path.join(BASE_DIR, "sleep-alert.mp3")

os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

# --- MediaPipe Face Mesh setup ---
_mp_face_mesh = mp.solutions.face_mesh
_face_mesh = _mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# Standard MediaPipe landmark indices for the 6 EAR points per eye
# (p1, p2, p3, p4, p5, p6 going around the eye)
LEFT_EYE_IDX = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_IDX = [33, 160, 158, 133, 153, 144]

# EAR drops sharply when eyes close. 0.21 is a common starting point;
# if your camera/lighting gives different numbers, tune this after
# checking printed EAR values (see DEBUG_PRINT_EAR below).
EAR_THRESHOLD = 0.21
DEBUG_PRINT_EAR = False  # set True temporarily to see live EAR values while tuning


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
    Runs MediaPipe Face Mesh on a BGR frame.
    Returns (face_coords, eyes_open, eye_points) where:
      - face_coords: (x, y, w, h) bounding box of the face, or None
      - eyes_open: bool, True if EAR indicates eyes are open
      - eye_points: list of (x, y) pixel coords for the eye landmarks (for drawing)
    """
    h, w = frame_bgr.shape[:2]
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    results = _face_mesh.process(rgb)

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


def draw_annotations(frame, face_coords, eyes_open, eye_points, alert_level, session_start_time, event_count):
    """Draw eye landmarks, borders, status text, and session stats on the frame."""
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
        border_color = (0, 200, 255)
        status_text = "Early Warning - Stay Alert"
        text_color = (0, 200, 255)

    else:
        border_thickness = 12
        border_color = (0, 255, 0)
        status_text = "Alert - Eyes Open" if eyes_open else "Watching..."
        text_color = (0, 255, 0)

    cv2.rectangle(output, (0, 0), (w - 1, h - 1), border_color, border_thickness)

    (text_w, text_h), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
    text_x = (w - text_w) // 2
    text_y = 50

    cv2.rectangle(
        output,
        (text_x - 15, text_y - text_h - 15),
        (text_x + text_w + 15, text_y + 10),
        (0, 0, 0),
        -1,
    )
    cv2.putText(
        output,
        status_text,
        (text_x, text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        text_color,
        2,
    )

    elapsed = int(time.time() - session_start_time)
    mins, secs = divmod(elapsed, 60)
    stats_text = f"Time: {mins:02d}:{secs:02d}  |  sleep events: {event_count}"
    cv2.putText(
        output,
        stats_text,
        (20, h - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    return output


def save_screenshot(frame):
    """Save frame with timestamp when a RED alert event occurs."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(SCREENSHOT_FOLDER, f"sleep_detection_{timestamp}.jpg")
    cv2.imwrite(filepath, frame)
    return filepath


class DetectorSession:
    """Per-user session state for web or desktop use."""

    def __init__(self):
        self.closed_counter = 0
        self.sleep_detection_event_count = 0
        self.yellow_warning_count = 0
        self.was_red_last_frame = False
        self.was_yellow_last_frame = False
        self.session_start_time = time.time()
        self.events = []          # list of {"time", "elapsed_seconds", "type"}
        self.total_frames = 0
        self.frames_with_eyes = 0

    def process_frame(self, frame, save_on_alert=True):
        face_coords, eyes_open, eye_points = detect_face_and_eyes(frame)

        self.total_frames += 1
        if eyes_open:
            self.frames_with_eyes += 1

        if not eyes_open:
            self.closed_counter += 1
        else:
            self.closed_counter = 0

        is_red = self.closed_counter >= RED_THRESHOLD_FRAMES
        is_yellow = (not is_red) and (self.closed_counter >= YELLOW_THRESHOLD_FRAMES)

        if is_red:
            alert_level = "red"
        elif is_yellow:
            alert_level = "yellow"
        else:
            alert_level = "green"

        new_event = False
        screenshot_path = None
        elapsed_now = int(time.time() - self.session_start_time)

        if is_red:
            if not self.was_red_last_frame:
                self.sleep_detection_event_count += 1
                new_event = True
                self.events.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "elapsed_seconds": elapsed_now,
                    "type": "Sleep Alert",
                })
                if save_on_alert:
                    screenshot_path = save_screenshot(frame)
        self.was_red_last_frame = is_red

        if is_yellow and not self.was_yellow_last_frame:
            self.yellow_warning_count += 1
            self.events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "elapsed_seconds": elapsed_now,
                "type": "Early Warning",
            })
        self.was_yellow_last_frame = is_yellow

        annotated = draw_annotations(
            frame,
            face_coords,
            eyes_open,
            eye_points,
            alert_level,
            self.session_start_time,
            self.sleep_detection_event_count,
        )

        elapsed = int(time.time() - self.session_start_time)
        mins, secs = divmod(elapsed, 60)

        return {
            "alert_level": alert_level,
            "annotated_frame": annotated,
            "eyes_found": 2 if eyes_open else 0,
            "face_detected": face_coords is not None,
            "closed_counter": self.closed_counter,
            "sleep_events": self.sleep_detection_event_count,
            "session_time": f"{mins:02d}:{secs:02d}",
            "play_sound": is_red,
            "new_event": new_event,
            "screenshot_path": screenshot_path,
        }

    def generate_report(self):
        """Build a session summary + event log for the end-of-session report."""
        elapsed = int(time.time() - self.session_start_time)
        mins, secs = divmod(elapsed, 60)
        attentiveness = (
            round((self.frames_with_eyes / self.total_frames) * 100, 1)
            if self.total_frames else 0.0
        )
        return {
            "session_start": datetime.fromtimestamp(self.session_start_time).strftime("%Y-%m-%d %H:%M:%S"),
            "session_end": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration": f"{mins:02d}:{secs:02d}",
            "duration_seconds": elapsed,
            "total_sleep_alerts": self.sleep_detection_event_count,
            "total_early_warnings": self.yellow_warning_count,
            "attentiveness_percent": attentiveness,
            "events": self.events,
        }