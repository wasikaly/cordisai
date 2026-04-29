"""
PyTorch Dataset for CAMUS (segmentation).
Each item: (image_tensor, mask_tensor) — single ED or ES frame.
"""
import numpy as np
import torch
import cv2
from torch.utils.data import Dataset
from pathlib import Path
from data.loaders.nifti_loader import load_camus_patient, normalize_image
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import CAMUS_NIFTI, IMG_SIZE


class CAMUSDataset(Dataset):
    """
    CAMUS 2D segmentation dataset.

    Yields (image, mask) pairs for ED and ES frames from all patients.
    Mask labels: 0=background, 1=LV cavity, 2=myocardium, 3=left atrium.

    Args:
        split:  'train' | 'val' | 'test'  (based on patient index split)
        view:   '4CH' | '2CH'
        phase:  'ED' | 'ES' | 'both'
    """

    # CAMUS split: 450 training patients, 50 test patients (patient0451-0500)
    TRAIN_RANGE = range(1, 451)
    TEST_RANGE = range(451, 501)

    def __init__(self, split: str = "train", view: str = "4CH",
                 phase: str = "both"):
        self.view = view
        self.phase = phase

        patient_range = self.TRAIN_RANGE if split == "train" else self.TEST_RANGE

        self.samples = []
        for i in patient_range:
            pid = f"patient{i:04d}"
            pdir = CAMUS_NIFTI / pid
            if not pdir.exists():
                continue
            if phase in ("ED", "both"):
                self.samples.append((pdir, "ED"))
            if phase in ("ES", "both"):
                self.samples.append((pdir, "ES"))

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        pdir, phase_key = self.samples[idx]
        data = load_camus_patient(pdir, view=self.view)

        image = normalize_image(data[phase_key])          # (H, W)
        mask = data[f"{phase_key}_gt"].astype(np.int64)   # (H, W) int labels

        # Resize to IMG_SIZE
        image = cv2.resize(image, (IMG_SIZE, IMG_SIZE),
                           interpolation=cv2.INTER_LINEAR)
        mask = cv2.resize(mask.astype(np.float32),
                          (IMG_SIZE, IMG_SIZE),
                          interpolation=cv2.INTER_NEAREST).astype(np.int64)

        # (H, W) → (1, H, W)
        img_tensor = torch.from_numpy(image).unsqueeze(0)
        mask_tensor = torch.from_numpy(mask)

        return img_tensor, mask_tensor
