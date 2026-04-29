"""
PyTorch Dataset for EchoNet-Dynamic.
Each item: (video_tensor, ef_label) where video_tensor is (1, T, H, W) float32.
"""
import pandas as pd
import numpy as np
import torch
from torch.utils.data import Dataset
from pathlib import Path
from data.loaders.video_loader import load_video
import sys, os
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import ECHONET_VIDEOS, ECHONET_FILELIST, IMG_SIZE


class EchoNetDataset(Dataset):
    """
    EchoNet-Dynamic A4C echo video dataset.

    Args:
        split:      'TRAIN', 'VAL', or 'TEST'
        max_frames: Clip / pad video to this length (None = keep all)
        transform:  Optional callable applied to the (1,T,H,W) tensor
    """

    def __init__(self, split: str = "TRAIN", max_frames: int = 128,
                 transform=None):
        self.split = split.upper()
        self.max_frames = max_frames
        self.transform = transform

        df = pd.read_csv(ECHONET_FILELIST)
        df = df[df["Split"] == self.split].reset_index(drop=True)
        self.df = df

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        fname = row["FileName"]
        ef = float(row["EF"])

        video_path = ECHONET_VIDEOS / f"{fname}.avi"
        # Evenly-sampled frames across the full video so the model sees
        # both systole and diastole — critical for accurate EF estimation.
        video = load_video(video_path, target_size=IMG_SIZE,
                           max_frames=self.max_frames,
                           sample_mode="evenly")         # (T, H, W)

        # (T, H, W) → (1, T, H, W)  channel-first for 3D convs
        tensor = torch.from_numpy(video).unsqueeze(0)

        if self.transform:
            tensor = self.transform(tensor)

        return tensor, torch.tensor(ef, dtype=torch.float32)

    def get_filename(self, idx: int) -> str:
        return self.df.iloc[idx]["FileName"]
