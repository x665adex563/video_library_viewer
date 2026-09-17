import os
import subprocess

COVER_CAPTURE_TIME = 80
COVER_WIDTH = 320
COVER_HEIGHT = 180

# --------------------
# 掃描是否有封面圖
# --------------------
def scan_missing_covers(videos, cover_folder):
    """
    掃描所有影片，回傳缺少封面圖的影片路徑清單
    """
    missing = []

    for video_path in videos:
        video_name = os.path.basename(video_path)
        cover_path = os.path.join(cover_folder, f"{video_name}.jpg")

        if not os.path.exists(cover_path):
            missing.append(video_path)

    return missing

# --------------------
# 封面圖生成
# --------------------
def generate_video_cover(
    video_path,
    cover_path,
    ffmpeg_exe,
    cancel_state,
):
    if cancel_state["requested"]:
        return

    if os.path.exists(cover_path):
        return

    os.makedirs(os.path.dirname(cover_path), exist_ok=True)

    # 自動判斷 ffmpeg 路徑
    if os.path.exists(ffmpeg_exe):
        ffmpeg_cmd = ffmpeg_exe
    else:
        ffmpeg_cmd = "ffmpeg"

    subprocess.run(
        [
            ffmpeg_cmd,
            "-ss", str(COVER_CAPTURE_TIME),
            "-i", video_path,
            "-frames:v", "1",
            "-vf", f"scale={COVER_WIDTH}:{COVER_HEIGHT}:force_original_aspect_ratio=decrease,"
                   f"pad={COVER_WIDTH}:{COVER_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
            cover_path
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

def ensure_default_cover(cover_folder):
    # 預設封面（黑底）
    default_cover = os.path.join(cover_folder, "default.jpg")

    if not os.path.exists(default_cover):
        from PIL import Image
        img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), color=(0, 0, 0))
        img.save(default_cover)

    return default_cover
