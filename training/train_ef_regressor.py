"""
Train EF Regression model on EchoNet-Dynamic.
Faster to train than segmentation — converges in ~20 epochs.
Saves checkpoint to checkpoints/ef_prediction.pt

Usage:
    python training/train_ef_regressor.py [--epochs 30] [--lr 5e-4] [--batch 16]
"""
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.amp import autocast, GradScaler
from tqdm import tqdm

from data.datasets.echonet_dataset import EchoNetDataset
from models.measurement.ef_regressor import EFRegressor
from config import CHECKPOINTS_DIR, DEVICE


def train(epochs: int = 30, lr: float = 5e-4, batch_size: int = 8,
          max_frames: int = 16, resume: bool = False):
    device = DEVICE if torch.cuda.is_available() else "cpu"
    use_amp = (device == "cuda")
    print(f"Training EF Regressor on: {device}  AMP={use_amp}  max_frames={max_frames}  resume={resume}")

    train_ds = EchoNetDataset(split="TRAIN", max_frames=max_frames)
    val_ds   = EchoNetDataset(split="VAL",   max_frames=max_frames)
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                          num_workers=0, pin_memory=use_amp)
    val_dl   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False,
                          num_workers=0)

    model = EFRegressor(pretrained=True).to(device)
    if resume:
        ckpt_path = CHECKPOINTS_DIR / "ef_prediction.pt"
        if ckpt_path.exists():
            model.load_state_dict(torch.load(ckpt_path, weights_only=True))
            print(f"Loaded weights from {ckpt_path}")
        else:
            print("No checkpoint found, starting from pretrained weights.")
        lr = lr / 10   # fine-tuning LR

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    if resume:
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    else:
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            optimizer, max_lr=lr,
            steps_per_epoch=len(train_dl), epochs=epochs,
        )
    criterion = nn.HuberLoss(delta=5.0)   # Huber: robust to outliers
    scaler    = GradScaler("cuda", enabled=use_amp)

    best_mae = float("inf")

    for epoch in range(1, epochs + 1):
        # ── Train ────────────────────────────────────────────────────────────
        model.train()
        train_loss = 0.0
        for videos, ef_labels in tqdm(train_dl,
                                       desc=f"Epoch {epoch}/{epochs} [train]",
                                       leave=False):
            # videos: (B, 1, T, H, W) → reshape to (B, T, 1, H, W)
            videos    = videos.permute(0, 2, 1, 3, 4).to(device)
            ef_labels = ef_labels.to(device)

            optimizer.zero_grad()
            with autocast("cuda", enabled=use_amp):
                preds = model(videos)
                loss  = criterion(preds, ef_labels)

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            if not resume:
                scheduler.step()   # OneCycleLR: per-batch step
            train_loss += loss.item()

        train_loss /= len(train_dl)
        if resume:
            scheduler.step()       # CosineAnnealingLR: per-epoch step

        # ── Validation ───────────────────────────────────────────────────────
        model.eval()
        mae_total, count = 0.0, 0
        with torch.no_grad():
            for videos, ef_labels in val_dl:
                videos    = videos.permute(0, 2, 1, 3, 4).to(device)
                ef_labels = ef_labels.to(device)
                with autocast("cuda", enabled=use_amp):
                    preds = model(videos)
                mae_total += (preds - ef_labels).abs().sum().item()
                count     += ef_labels.size(0)

        val_mae = mae_total / count
        print(f"Epoch {epoch:03d} | loss={train_loss:.4f} | val_MAE={val_mae:.2f}%")

        if val_mae < best_mae:
            best_mae = val_mae
            torch.save(model.state_dict(),
                       CHECKPOINTS_DIR / "ef_prediction.pt")
            print(f"  [+] Saved best checkpoint (MAE={best_mae:.2f}%)")

        # Free fragmented VRAM between epochs to prevent OOM on long runs
        if use_amp:
            torch.cuda.empty_cache()
        sys.stdout.flush()
        sys.stderr.flush()

    print(f"\nDone. Best Val MAE: {best_mae:.2f}%")
    print(f"Checkpoint: {CHECKPOINTS_DIR / 'ef_prediction.pt'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs",     type=int,   default=30)
    parser.add_argument("--lr",         type=float, default=5e-4)
    parser.add_argument("--batch",      type=int,   default=8)
    parser.add_argument("--max_frames", type=int,   default=16)
    parser.add_argument("--resume",     action="store_true",
                        help="Resume from checkpoint with LR/10 and CosineAnnealingLR")
    args = parser.parse_args()
    train(args.epochs, args.lr, args.batch, args.max_frames, args.resume)
