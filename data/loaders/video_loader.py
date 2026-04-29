"""
Video / AVI loader for EchoNet-Dynamic.
Returns a (T, H, W) numpy array of grayscale frames (float32, [0, 1]).
"""
import cv2
import numpy as np
from pathlib import Path


def _open_capture(path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {path}")
    return cap


def load_video(path: str | Path, target_size: int = 112,
               max_frames: int | None = None,
               sample_mode: str = "evenly") -> np.ndarray:
    """
    Load an AVI echo video and return float32 tensor (T, H, W).

    Args:
        path:        Path to .avi file.
        target_size: Resize each frame to (target_size, target_size).
        max_frames:  If set, limit to this many frames.
        sample_mode: How to select frames when max_frames < total frames.
                     'evenly'  — evenly-spaced indices across the full video
                                 (captures full cardiac cycle; default).
                     'center'  — consecutive frames from the video centre.
                     'all'     — read all frames (ignores max_frames limit).

    Returns:
        np.ndarray of shape (T, H, W), dtype float32, values in [0, 1].
    """
    cap = _open_capture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if max_frames is None or sample_mode == "all":
        # Sequential read of all frames
        indices = None
    elif sample_mode == "evenly":
        # Evenly-spaced indices — covers systole AND diastole
        n = min(max_frames, total)
        indices = np.linspace(0, total - 1, n, dtype=int)
    else:  # "center"
        start = max(0, (total - max_frames) // 2)
        n = min(max_frames, total - start)
        indices = np.arange(start, start + n, dtype=int)

    frames = []
    if indices is None:
        # Read sequentially
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if gray.shape[0] != target_size or gray.shape[1] != target_size:
                gray = cv2.resize(gray, (target_size, target_size),
                                  interpolation=cv2.INTER_LINEAR)
            frames.append(gray)
    else:
        # Seek to each target index individually
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if gray.shape[0] != target_size or gray.shape[1] != target_size:
                gray = cv2.resize(gray, (target_size, target_size),
                                  interpolation=cv2.INTER_LINEAR)
            frames.append(gray)
    cap.release()

    if not frames:
        raise ValueError(f"No frames read from {path}")

    video = np.stack(frames, axis=0).astype(np.float32) / 255.0  # (T, H, W)

    # Pad to max_frames if video is shorter (repeat last frame)
    if max_frames is not None and sample_mode != "all" and video.shape[0] < max_frames:
        pad = np.repeat(video[-1:], max_frames - video.shape[0], axis=0)
        video = np.concatenate([video, pad], axis=0)

    return video


def get_video_metadata(path: str | Path) -> dict:
    """Return basic metadata dict for a video file."""
    cap = _open_capture(path)
    meta = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    cap.release()
    return meta
