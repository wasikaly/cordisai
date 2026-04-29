"""
Segmentation inference: load checkpoint, run on echo frames.
Returns per-frame masks (T, H, W) for an entire video.
"""
import torch
import numpy as np
from pathlib import Path
from models.segmentation.unet import UNet
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import SEG_CHECKPOINT, DEVICE, IMG_SIZE


_model: UNet | None = None


def has_checkpoint() -> bool:
    """Return True if a trained segmentation checkpoint exists."""
    return SEG_CHECKPOINT.exists()


def _get_model(device: str) -> UNet:
    global _model
    if _model is None:
        _model = UNet(in_channels=1, num_classes=4).to(device)
        if SEG_CHECKPOINT.exists():
            state = torch.load(SEG_CHECKPOINT, map_location=device,
                               weights_only=True)
            _model.load_state_dict(state)
            print(f"[Segmentation] Loaded checkpoint: {SEG_CHECKPOINT}")
        else:
            print("[Segmentation] No checkpoint found - using random weights. "
                  "Run training/train_segmentation.py first.")
        _model.eval()
    return _model


def segment_video(video: np.ndarray, device: str = DEVICE,
                  batch_size: int = 16) -> np.ndarray:
    """
    Segment all frames of an echo video.

    Args:
        video:      (T, H, W) float32 [0,1] grayscale frames
        device:     'cuda' or 'cpu'
        batch_size: Frames per inference batch

    Returns:
        masks: (T, H, W) int64 class labels
               0=background, 1=LV_endo, 2=myocardium, 3=LA
    """
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    model = _get_model(device)
    T, H, W = video.shape
    masks = np.zeros((T, H, W), dtype=np.int64)

    for i in range(0, T, batch_size):
        batch = video[i: i + batch_size]                    # (B, H, W)
        tensor = torch.from_numpy(batch).unsqueeze(1).to(device)  # (B,1,H,W)
        with torch.no_grad():
            pred = model(tensor).argmax(dim=1).cpu().numpy()  # (B, H, W)
        masks[i: i + batch_size] = pred

    return masks


def segment_frame(frame: np.ndarray, device: str = DEVICE) -> np.ndarray:
    """
    Segment a single (H, W) frame. Returns (H, W) int mask.
    """
    video = frame[np.newaxis]   # (1, H, W)
    return segment_video(video, device=device)[0]
