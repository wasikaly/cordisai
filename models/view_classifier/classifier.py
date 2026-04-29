"""
Echo View Classifier — identifies the echocardiography view from a video.

Supported views:
  0 = A4C  (Apical 4-Chamber)  — primary view for LVEF
  1 = A2C  (Apical 2-Chamber)
  2 = PLAX (Parasternal Long Axis) — wall thickness
  3 = PSAX (Parasternal Short Axis)
  4 = Other / Unknown

Architecture: EfficientNet-B0 frame encoder → temporal mean pool → 5-class head.
Trained on EchoNet-Dynamic (all A4C) + HMC-QU (A4C/A2C labels).
For MVP: uses simple heuristics when no checkpoint is available.
"""
import torch
import torch.nn as nn
import numpy as np
import timm
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import CHECKPOINTS_DIR

VIEW_LABELS = ["A4C", "A2C", "PLAX", "PSAX", "Other"]
VIEW_CHECKPOINT = CHECKPOINTS_DIR / "view_classifier.pt"


class ViewClassifier(nn.Module):
    """
    EfficientNet-B0 per-frame encoder + temporal mean pool → 5-class view head.
    Input: (B, T, 1, H, W) or (B, 1, H, W) grayscale video tensor.
    Output: (B, 5) logits.
    """

    def __init__(self, pretrained: bool = True, drop_rate: float = 0.3):
        super().__init__()
        self.encoder = timm.create_model(
            "efficientnet_b0", pretrained=pretrained,
            num_classes=0, in_chans=1, global_pool="avg",
        )
        embed_dim = self.encoder.num_features
        self.head = nn.Sequential(
            nn.Dropout(drop_rate),
            nn.Linear(embed_dim, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, len(VIEW_LABELS)),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim == 5:
            B, T, C, H, W = x.shape
            feats = self.encoder(x.view(B * T, C, H, W)).view(B, T, -1).mean(1)
        else:
            feats = self.encoder(x)
        return self.head(feats)


# ── Singleton inference ────────────────────────────────────────────────────────

_view_model: ViewClassifier | None = None


def _get_view_model(device: str) -> ViewClassifier | None:
    global _view_model
    if _view_model is None:
        if not VIEW_CHECKPOINT.exists():
            return None
        _view_model = ViewClassifier(pretrained=False).to(device)
        state = torch.load(VIEW_CHECKPOINT, map_location=device, weights_only=True)
        _view_model.load_state_dict(state)
        _view_model.eval()
        print(f"[ViewClassifier] Loaded checkpoint: {VIEW_CHECKPOINT}")
    return _view_model


def classify_view(video: np.ndarray, device: str = "cuda") -> dict:
    """
    Classify the echo view of a video.

    Args:
        video:  (T, H, W) float32 frames.
        device: 'cuda' or 'cpu'.

    Returns:
        {
          'view':       str  — e.g. 'A4C',
          'confidence': float [0, 1],
          'all_scores': dict  — {view_name: probability},
          'trained':    bool  — False if checkpoint missing (fallback used),
        }
    """
    if device == "cuda" and not torch.cuda.is_available():
        device = "cpu"

    model = _get_view_model(device)

    if model is None:
        # Heuristic fallback: assume A4C (EchoNet-Dynamic standard)
        return {
            "view": "A4C",
            "confidence": 0.0,
            "all_scores": {v: (1.0 if v == "A4C" else 0.0) for v in VIEW_LABELS},
            "trained": False,
        }

    # Sample up to 16 evenly-spaced frames for speed
    T = video.shape[0]
    indices = np.linspace(0, T - 1, min(T, 16), dtype=int)
    frames = video[indices]                                   # (16, H, W)
    tensor = torch.from_numpy(frames).unsqueeze(1).unsqueeze(0).to(device)  # (1,16,1,H,W)

    with torch.no_grad():
        logits = model(tensor)                                # (1, 5)
        probs = logits.softmax(dim=1)[0].cpu().numpy()

    idx = int(probs.argmax())
    return {
        "view":       VIEW_LABELS[idx],
        "confidence": float(probs[idx]),
        "all_scores": {v: float(p) for v, p in zip(VIEW_LABELS, probs)},
        "trained":    True,
    }
