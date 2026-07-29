# Argus Vision

**A real-time drowsiness detector, built with computer vision.**

Argus watches your eyes through your webcam. If you start to fall asleep, it warns you while driving, studying late, or working long hours.

🔗 **Live demo:** [web-production-1a993.up.railway.app](https://web-production-1a993.up.railway.app)

---

## What It Does

- Watches your eyes in real time using face landmark detection
- Uses **Eye Aspect Ratio (EAR)** to check if your eyes are open or closed — this works better than simple pattern matching
- Has 3 alert levels: **green** (you're alert), **yellow** (early warning), **red** (wake-up alarm with sound)
- Creates a **PDF report** at the end of each session — shows session time, number of alerts, and an attentiveness score
- Works fully in the browser : no app to install, just a webcam and a browser tab

---

## Tech Stack

| Layer | Tools |
|---|---|
| Computer Vision | MediaPipe Face Mesh, OpenCV, NumPy |
| Backend | Flask, Gunicorn |
| Data / Reports | Pandas (for counting alerts and analyzing event timing), ReportLab (for making the PDF) |
| Frontend | HTML, CSS, plain JavaScript (Canvas API, MediaDevices API) |
| Infra | Docker, Railway |

---

## How Detection Works

Many older drowsiness-detection projects use Haar Cascades to find where the eyes are. But that only tells you *there is an eye there* — not if it's open or closed. Argus instead uses **MediaPipe's face mesh** (468 points on the face) to find exact eye points, then calculates the **Eye Aspect Ratio**:

```
EAR = (|p2 - p6| + |p3 - p5|) / (2 * |p1 - p4|)
```

When an eye is open, this number is high. When it starts to close, the number drops fast. Checking this every frame gives a much more accurate result than just detecting "is there an eye here."

**NumPy** does the math behind this — measuring distances for the EAR formula, turning webcam frames into pixel arrays, and drawing the red/yellow alert overlays on the video.

**Pandas** is used at the end of a session. All the alert/warning events (with their timestamps) get loaded into a table (DataFrame), so it can count how many of each type happened and work out the average time between alerts. These numbers go into the PDF report and a separate CSV file.

---

## Project Structure

```
argus-vision/
├── app.py                  # Flask app + API routes
├── detector_core.py        # MediaPipe/EAR detection logic, session state
├── report_pdf.py            # Builds the PDF report (ReportLab)
├── requirements.txt
├── Dockerfile
├── Procfile                 # For platforms that don't use Docker (like Render buildpacks)
├── .env.example              # Shows which environment variables are needed
├── templates/
│   └── index.html            # Full frontend (HTML/CSS/JS in one file)
├── Audio/                     # Intro voice, alert tone, monitoring sound
└── video/                     # Background animation for the idle screen
```

---

## Running It Locally

**1. Clone the repo**
```bash
git clone https://github.com/fahadware/argus-vision.git
cd argus-vision
```

**2. Install the requirements**
```bash
pip install -r requirements.txt
```

**3. Set up your environment file**
```bash
cp .env.example .env
# then open .env and set a real FLASK_SECRET_KEY
```

**4. Run the app**
```bash
python app.py
```
Go to `http://localhost:5000`, allow camera access, and click **Start Monitoring**.

---

## Running With Docker

```bash
docker build -t argus-vision .
docker run --rm -p 5000:5000 --env-file .env argus-vision
```

---

## Deployment

This app is deployed on [Railway](https://railway.app) using the `Dockerfile` in this repo. The environment variables (`FLASK_SECRET_KEY`, `FLASK_DEBUG`, `LOG_LEVEL`) are set inside Railway's dashboard, not committed to the code.

**Note about free hosting:** session reports and screenshots are stored on temporary disk space. They get wiped when the app redeploys or sleeps for a while. To keep them permanently, this would need external storage like S3 in the future.

---

## Limitations

- Detection accuracy depends on lighting and camera angle — the EAR threshold might need adjusting for different setups
- Free hosting means the app can be slow to wake up after being inactive
- Only detects one face at a time this is intentional, for personal use

---

## Built By

**Fahad**-learning AI engineering .

This project went through a few versions. It started with Haar Cascades, which weren't reliable at telling open eyes from closed ones, so the detection logic was rebuilt using MediaPipe + EAR instead. Along the way, this project also became a hands on lesson in Docker, environment variables, and fixing a real concurrency bug (a shared MediaPipe object causing errors when multiple requests came in at the same time).