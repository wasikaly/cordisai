"""
Train U-Net segmentation model on CAMUS dataset.
Saves best checkpoint to checkpoints/segmentation.pt

Usage:
    python training/train_segmentation.py [--epochs 60] [--lr 1e-3] [--batch 8]
    python training/train_segmentation.py --resume   # continue from checkpoint
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

from data.datasets.camus_dataset import CAMUSDataset
from models.segmentation.unet import UNet
from config import CHECKPOINTS_DIR, DEVICE


def dice_loss(pred: torch.Tensor, target: torch.Tensor,
              num_classes: int = 4, smooth: float = 1e-6) -> torch.Tensor:
    """Soft Dice loss averaged over classes."""
    pred_soft = pred.softmax(dim=1)
    total = 0.0
    for c in range(num_classes):
        p = pred_soft[:, c]
        t = (target == c).float()
        intersection = (p * t).sum()
        total += 1 - (2 * intersection + smooth) / (p.sum() + t.sum() + smooth)
    return total / num_classes


def train(epochs: int = 60, lr: float = 1e-3, batch_size: int = 8,
          view: str = "4CH", resume: bool = False):
    device = DEVICE if torch.cuda.is_available() else "cpu"
    use_amp = (device == "cuda")
    print(f"Training on: {device}  AMP={use_amp}")

    train_ds = CAMUSDataset(split="train", view=view, phase="both")
    val_ds   = CAMUSDataset(split="test",  view=view, phase="both")
    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                          num_workers=0, pin_memory=use_amp)
    val_dl   = DataLoader(val_ds, batch_size=batch_size, shuffle=False,
                          num_workers=0)

    model = UNet(in_channels=1, num_classes=4, base_features=32).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    ce_loss   = nn.CrossEntropyLoss()
    scaler    = GradScaler("cuda", enabled=use_amp)

    best_val_dice = 0.0
    ckpt = CHECKPOINTS_DIR / "segmentation.pt"

    if resume and ckpt.exists():
        state = torch.load(ckpt, map_location=device, weights_only=True)
        model.load_state_dict(state)
        print(f"[Resume] Loaded checkpoint from {ckpt}")
        # Quick val to establish baseline dice
        model.eval()
        val_dice = 0.0
        with torch.no_grad():
            for imgs, masks in val_dl:
                imgs = imgs.to(device); masks = masks.to(device)
                pred = model(imgs).argmax(dim=1)
                p = (pred == 1).float(); t = (masks == 1).float()
                dice = (2*(p*t).sum()+1e-6)/(p.sum()+t.sum()+1e-6)
                val_dice += dice.item()
        best_val_dice = val_dice / len(val_dl)
        print(f"[Resume] Current val LV Dice: {best_val_dice:.4f}")
        model.train()

    for epoch in range(1, epochs + 1):
        # ── Train ────────────────────────────────────────────────────────────
        model.train()
        train_loss = 0.0
        for imgs, masks in tqdm(train_dl, desc=f"Epoch {epoch}/{epochs} [train]",
                                leave=False):
            imgs  = imgs.to(device)
            masks = masks.to(device)

            optimizer.zero_grad()
            with autocast("cuda", enabled=use_amp):
                logits = model(imgs)
                loss   = ce_loss(logits, masks) + dice_loss(logits, masks)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            train_loss += loss.item()

        scheduler.step()
        train_loss /= len(train_dl)

        # ── Validation ───────────────────────────────────────────────────────
        model.eval()
        val_dice = 0.0
        with torch.no_grad():
            for imgs, masks in val_dl:
                imgs  = imgs.to(device)
                masks = masks.to(device)
                logits = model(imgs)
                pred   = logits.argmax(dim=1)

                # LV Dice (class 1)
                p = (pred == 1).float()
                t = (masks == 1).float()
                dice = (2 * (p * t).sum() + 1e-6) / (p.sum() + t.sum() + 1e-6)
                val_dice += dice.item()

        val_dice /= len(val_dl)

        print(f"Epoch {epoch:03d} | train_loss={train_loss:.4f} | "
              f"val_lv_dice={val_dice:.4f}")

        if val_dice > best_val_dice:
            best_val_dice = val_dice
            torch.save(model.state_dict(), CHECKPOINTS_DIR / "segmentation.pt")
            print(f"  [+] Saved best checkpoint (dice={best_val_dice:.4f})")

    print(f"\nTraining complete. Best LV Dice: {best_val_dice:.4f}")
    print(f"Checkpoint: {CHECKPOINTS_DIR / 'segmentation.pt'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs",     type=int,   default=60)
    parser.add_argument("--lr",         type=float, default=1e-3)
    parser.add_argument("--batch",      type=int,   default=8)
    parser.add_argument("--view",       type=str,   default="4CH",
                        choices=["4CH", "2CH"])
    parser.add_argument("--resume",     action="store_true",
                        help="Resume from existing checkpoint")
    args = parser.parse_args()
    train(args.epochs, args.lr, args.batch, args.view, args.resume)
