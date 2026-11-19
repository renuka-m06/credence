import subprocess
import time
import sys
from pathlib import Path
import urllib.request
import shutil

edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
out_png = Path(r"c:\Users\PoornaTeja Shree\OneDrive\Desktop\credence\report_screen.png")
brain_dir = Path(r"C:\Users\PoornaTeja Shree\.gemini\antigravity\brain\7dc92f76-135e-439d-89cd-d3deb0c52543")

port = 5174
print(f"Starting python http.server on port {port}...")
server = subprocess.Popen(
    [sys.executable, "-m", "http.server", str(port), "--directory", "frontend/dist"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    cwd=r"c:\Users\PoornaTeja Shree\OneDrive\Desktop\credence"
)

try:
    time.sleep(1.5)
    # Now run Edge to take screenshot
    cmd = [
        edge_path,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-proxy-server",
        "--user-data-dir=" + str(Path.home() / "AppData" / "Local" / "Temp" / "edge_credence_temp_5174"),
        "--window-size=1400,1200",
        f"--screenshot={str(out_png)}",
        f"http://127.0.0.1:{port}"
    ]
    print("Running Edge:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    print("Edge returncode:", res.returncode)

    if out_png.exists():
        print(f"Screenshot successfully created at: {out_png} (size: {out_png.stat().st_size} bytes)")
        brain_png = brain_dir / "report_screen.png"
        shutil.copy2(out_png, brain_png)
        print(f"Copied to brain dir: {brain_png}")
    else:
        print("Screenshot file was NOT created.")

finally:
    server.terminate()
    try:
        server.wait(timeout=2)
    except Exception:
        server.kill()
    print("Static server stopped.")
