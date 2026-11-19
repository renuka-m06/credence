import subprocess
import time
import sys
from pathlib import Path
import shutil

edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
brain_dir = Path(r"C:\Users\PoornaTeja Shree\.gemini\antigravity\brain\7dc92f76-135e-439d-89cd-d3deb0c52543")

port = 5176
print(f"Starting python http.server on port {port}...")
server = subprocess.Popen(
    [sys.executable, "-m", "http.server", str(port), "--directory", "frontend/dist"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    cwd=r"c:\Users\PoornaTeja Shree\OneDrive\Desktop\credence"
)

captures = [
    ("home_dark.png", f"http://127.0.0.1:{port}/?theme=dark"),
    ("home_light.png", f"http://127.0.0.1:{port}/?theme=light"),
    ("dossier_dark.png", f"http://127.0.0.1:{port}/?screen=report&theme=dark"),
    ("dossier_light.png", f"http://127.0.0.1:{port}/?screen=report&theme=light"),
]

try:
    time.sleep(1.5)
    for filename, url in captures:
        out_png = Path(rf"c:\Users\PoornaTeja Shree\OneDrive\Desktop\credence\{filename}")
        cmd = [
            edge_path,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-proxy-server",
            "--user-data-dir=" + str(Path.home() / "AppData" / "Local" / "Temp" / f"edge_credence_temp_{port}"),
            "--window-size=1440,1100",
            f"--screenshot={str(out_png)}",
            url
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if out_png.exists():
            print(f"Captured {filename} ({out_png.stat().st_size} bytes)")
            shutil.copy2(out_png, brain_dir / filename)
        else:
            print(f"Failed to capture {filename}")

finally:
    server.terminate()
    try:
        server.wait(timeout=2)
    except Exception:
        server.kill()
    print("Server stopped.")
