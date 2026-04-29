"""
Train Echo View Classifier.

Dataset (two classes with available data):
  - EchoNet-Dynamic AVI videos   -> A4C (class 0)
  - CAMUS NIfTI 4CH sequences    -> A4C (class 0)
  - CAMUS NIfTI 2CH sequences    -> A2C (class 1)

The ViewClassifier head has 5 outputs; only A4C and A2C are present in
training.  PLAX / PSAX / Other can be added later with more data.

Usage:
    python training/train_view_classifier.py [--epochs 20] [--lr 1e-3] [--batch 16]
"""
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, ConcatDataset
from torch.amp import autocast, GradScaler
import numpy as np
import pandas as pd
from tqdm import tqdm

from data.loaders.video_loader import load_video
from data.loaders.nifti_loader import load_nifti, normalize_image
from models.view_classifier.classifier import ViewClassifier
from config import (CHECKPOINTS_DIR, DEVICE, ECHONET_VIDEOS, ECHONET_FILELIST,
                    IMG_SIZE, CAMUS_NIFTI)


# ── Datasets ────────────────────────────────────────────────────────────────────

class EchoNetA4CDataset(Dataset):
    """
    EchoNet-Dynamic videos — all A4C (class 0).
    Returns one random frame per video as (1, H, W) tensor.
    """

    def __init__(self, split: str = "TRAIN"):
        df = pd.read_csv(ECHONET_FILELIST)
        self.df = df[df["Split"] == split.upper()].reset_index(drop=True)

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int):
        fname = self.df.iloc[idx]["FileName"]
        video = load_video(ECHONET_VIDEOS / f"{fname}.avi",
                           target_size=IMG_SIZE)           # (T, H, W)
        frame = video[np.random.randint(len(video))]       # (H, W)
        tensor = torch.from_numpy(frame).unsqueeze(0)      # (1, H, W)
        return tensor, torch.tensor(0, dtype=torch.long)   # A4C = 0


class CamusViewDataset(Dataset):
    """
    CAMUS NIfTI dataset with two views:
      4CH sequence  -> A4C (class 0)
      2CH sequence  -> A2C (class 1)

    Each sample is one random frame from a sequence.
    80/20 patient-level split is used when split='TRAIN' / 'VAL'.
    """

    def __init__(self, split: str = "TRAIN"):
        camus_dir = Path(CAMUS_NIFTI)
        patients = sorted(p for p in camus_dir.iterdir() if p.is_dir())
        rng = np.random.default_rng(42)
        rng.shuffle(patients)
        cut = int(0.8 * len(patients))
        patients = patients[:cut] if split.upper() == "TRAIN" else patients[cut:]

        self.items = []   # (path, label)
        for p in patients:
            seq4 = p / f"{p.name}_4CH_half_sequence.nii.gz"
            seq2 = p / f"{p.name}_2CH_half_sequence.nii.gz"
            if seq4.exists():
                self.items.append((seq4, 0))   # A4C
            if seq2.exists():
                self.items.append((seq2, 1))   # A2C

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int):
        path, label = self.items[idx]
        arr = load_nifti(path)                          # (T, H, W) or (H, W, T)
        if arr.ndim == 3:
            # Ensure temporal axis first: if last dim is much smaller it's likely T
            if arr.shape[0] < arr.shape[-1]:
                arr = arr.transpose(2, 0, 1)            # (H, W, T) -> (T, H, W)
            frame = arr[np.random.randint(arr.shape[0])]
        else:
            frame = arr
        frame = normalize_image(frame).astype(np.float32)
        if frame.shape[0] != IMG_SIZE or frame.shape[1] != IMG_SIZE:
            import cv2
            frame = cv2.resize(frame, (IMG_SIZE, IMG_SIZE),
                               interpolation=cv2.INTER_LINEAR)
        tensor = torch.from_numpy(frame).unsqueeze(0)   # (1, H, W)
        return tensor, torch.tensor(label, dtype=torch.long)


# ── Training ────────────────────────────────────────────────────────────────────

def train(epochs: int = 20, lr: float = 1e-3, batch_size: int = 16):
    device = DEVICE if torch.cuda.is_available() else "cpu"
    use_amp = (device == "cuda")
    print(f"Training View Classifier on: {device}  AMP={use_amp}")

    # Build combined datasets
    echonet_train = EchoNetA4CDataset(split="TRAIN")
    echonet_val   = EchoNetA4CDataset(split="VAL")
    camus_train   = CamusViewDataset(split="TRAIN")
    camus_val     = CamusViewDataset(split="VAL")

    train_ds = ConcatDataset([echonet_train, camus_train])
    val_ds   = ConcatDataset([echonet_val,   camus_val])

    # Summarise class balance (count from .items to avoid loading all files)
    camus_a4c = sum(1 for _, l in camus_train.items if l == 0)
    camus_a2c = sum(1 for _, l in camus_train.items if l == 1)
    total_a4c = len(echonet_train) + camus_a4c
    print(f"Train: {len(train_ds)} samples  (A4C={total_a4c}, A2C={camus_a2c})")

    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                          num_workers=0, pin_memory=use_amp)
    val_dl   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False,
                          num_workers=0)

    model     = ViewClassifier(pretrained=True).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    # Weighted loss to compensate for A4C >> A2C imbalance
    n_total = total_a4c + camus_a2c
    w_a4c = n_total / (2 * max(total_a4c, 1))
    w_a2c = n_total / (2 * max(camus_a2c, 1))
    class_weights = torch.tensor([w_a4c, w_a2c, 1.0, 1.0, 1.0]).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    scaler    = GradScaler("cuda", enabled=use_amp)

    best_acc = 0.0

    for epoch in range(1, epochs + 1):
        # ── Train ────────────────────────────────────────────────────────────
        model.train()
        train_loss = 0.0
        for frames, labels in tqdm(train_dl,
                                   desc=f"Epoch {epoch}/{epochs} [train]",
                                   leave=False):
            frames = frames.to(device)
            labels = labels.to(device)
            optimizer.zero_grad()
            with autocast("cuda", enabled=use_amp):
                logits = model(frames)
                loss   = criterion(logits, labels)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            train_loss += loss.item()

        scheduler.step()
        train_loss /= len(train_dl)

        # ── Validation ───────────────────────────────────────────────────────
        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for frames, labels in val_dl:
                frames = frames.to(device)
                labels = labels.to(device)
                with autocast("cuda", enabled=use_amp):
                    preds = model(frames).argmax(dim=1)
                correct += (preds == labels).sum().item()
                total   += labels.size(0)

        val_acc = correct / total
        print(f"Epoch {epoch:03d} | loss={train_loss:.4f} | val_acc={val_acc:.4f}")

        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), CHECKPOINTS_DIR / "view_classifier.pt")
            print(f"  [+] Saved best checkpoint (acc={best_acc:.4f})")

        # Always save last epoch so training can resume from here
        torch.save({
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "val_acc": val_acc,
            "best_acc": best_acc,
        }, CHECKPOINTS_DIR / "view_classifier_last.pt")

        if use_amp:
            torch.cuda.empty_cache()

    print(f"\nDone. Best val accuracy: {best_acc:.4f}")
    print(f"Best checkpoint:  {CHECKPOINTS_DIR / 'view_classifier.pt'}")
    print(f"Last checkpoint:  {CHECKPOINTS_DIR / 'view_classifier_last.pt'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int,   default=20)
    parser.add_argument("--lr",     type=float, default=1e-3)
    parser.add_argument("--batch",  type=int,   default=16)
    args = parser.parse_args()
    train(args.epochs, args.lr, args.batch)
