"""
EF Regression model — direct LVEF prediction from echo video.
Architecture: EfficientNet-B0 frame encoder + temporal mean pooling + MLP head.
Input:  (B, T, 1, H, W) float32 video tensor
Output: (B,) LVEF in %

This is the "fast path" that doesn't require segmentation.
Used when segmentation checkpoint is not yet available.
"""
import torch
import torch.nn as nn
import timm


class EFRegressor(nn.Module):
    """
    Per-frame EfficientNet encoder with temporal mean pooling for LVEF regression.
    """

    def __init__(self, backbone: str = "efficientnet_b0",
                 pretrained: bool = True, drop_rate: float = 0.3):
        super().__init__()
        # Frame encoder — convert 1-channel gray to 3-channel for pretrained model
        self.encoder = timm.create_model(
            backbone, pretrained=pretrained,
            num_classes=0,          # Remove classifier head
            in_chans=1,             # Single-channel input
            global_pool="avg",
        )
        embed_dim = self.encoder.num_features

        self.head = nn.Sequential(
            nn.Dropout(drop_rate),
            nn.Linear(embed_dim, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(drop_rate / 2),
            nn.Linear(256, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, T, 1, H, W) video tensor  OR  (B, 1, H, W) single frame
        Returns:
            ef: (B,) predicted LVEF values
        """
        if x.ndim == 5:
            B, T, C, H, W = x.shape
            # Encode each frame independently, then pool over T
            x_flat = x.view(B * T, C, H, W)        # (B*T, 1, H, W)
            feats   = self.encoder(x_flat)           # (B*T, D)
            feats   = feats.view(B, T, -1).mean(1)  # (B, D) temporal mean
        else:
            feats = self.encoder(x)                  # (B, D)

        return self.head(feats).squeeze(-1)          # (B,)
