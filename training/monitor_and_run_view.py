"""
Monitors EF Regressor training and auto-starts View Classifier when done.
Run with: python training/monitor_and_run_view.py
"""
import re
import os
import sys
import time
import subprocess
from pathlib import Path

EF_LOG   = Path("training/logs/ef_resume.log")
VIEW_LOG = Path("training/logs/view_classifier.log")
POLL_SEC = 20

seen_epochs = set()
best_mae = None

def parse_log():
    text = EF_LOG.read_text(encoding="utf-8", errors="replace")
    epochs = re.findall(
        r'Epoch (\d+) \| loss=([\d.]+) \| val_MAE=([\d.]+)%',
        text
    )
    saved = re.findall(r'Saved best checkpoint \(MAE=([\d.]+)%\)', text)
    done = "Training complete" in text or ("View Classifier" in text)
    return epochs, saved, done

print("=" * 60)
print("HeartAI training monitor")
print(f"EF log: {EF_LOG}")
print("=" * 60)
sys.stdout.flush()

while True:
    if not EF_LOG.exists():
        print(f"Waiting for {EF_LOG} ...")
        time.sleep(POLL_SEC)
        continue

    epochs, saved, done = parse_log()
    best_mae = saved[-1] if saved else None

    for ep, loss, mae in epochs:
        key = ep
        if key not in seen_epochs:
            seen_epochs.add(key)
            marker = " <-- BEST" if mae == best_mae else ""
            print(f"Epoch {ep}/30 | loss={loss} | val_MAE={mae}%{marker}")
            sys.stdout.flush()

    if done:
        print()
        print(f"EF Regressor finished. Best MAE: {best_mae}%")
        print("Starting View Classifier...")
        sys.stdout.flush()
        VIEW_LOG.parent.mkdir(exist_ok=True)
        with open(VIEW_LOG, "a") as log_f:
            proc = subprocess.run(
                [sys.executable, "training/train_view_classifier.py",
                 "--epochs", "20", "--lr", "1e-3", "--batch", "16"],
                stdout=log_f, stderr=log_f, text=True,
            )
        print(f"View Classifier done (exit={proc.returncode}). Log: {VIEW_LOG}")
        break

    time.sleep(POLL_SEC)
