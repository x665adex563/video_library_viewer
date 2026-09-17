import os
import sys
from tkinter import Tk, filedialog, messagebox
from cover_generator import scan_missing_covers
from video_library_viewer import (
    count_all_videos,
    create_progress_window,
    generate_index_html,
    get_all_videos,
    open_index,
)

def main():
    allow_generate_cover = True
    cancel_state = {"requested": False}
    root = Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="選擇影片資料夾")
    if not folder:
        exit()

    SOURCE_ROOT = folder   # 原始影片根目錄

    if getattr(sys, 'frozen', False):
        APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
    else:
        APP_DIR = os.path.dirname(os.path.abspath(__file__))

    ffmpeg_exe = os.path.join(APP_DIR, "ffmpeg", "bin", "ffmpeg.exe")

    OUTPUT_DIR = os.path.join(APP_DIR, "_preview_image_editor_output")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    video_folder_name = os.path.basename(folder)
    viewer_folder = os.path.join(OUTPUT_DIR, video_folder_name)
    os.makedirs(viewer_folder, exist_ok=True)

    # HTML
    html_folder = os.path.join(viewer_folder, "html")
    os.makedirs(html_folder, exist_ok=True)

    # 封面
    cover_folder = os.path.join(viewer_folder, "covers")
    os.makedirs(cover_folder, exist_ok=True)

    videos = get_all_videos(SOURCE_ROOT)
    missing_covers = scan_missing_covers(videos, cover_folder)

    if missing_covers:
        answer = messagebox.askyesno(
            "缺少封面圖",
            f"發現 {len(missing_covers)} 個影片缺少封面圖，是否要生成？\n\n"
            "選「否」將跳過封面生成（HTML 仍會建立）"
        )
        if not answer:
            allow_generate_cover = False

    # 生成首頁前再判斷是否要顯示進度視窗
    total_videos = count_all_videos(SOURCE_ROOT)
    processed_videos = 0


    if allow_generate_cover:
        progress_win, progress_label = create_progress_window(
            root,
            total_videos,
            cancel_state,
        )

    else:
        progress_win = None
        progress_label = None

    def update_progress(processed_videos, total_videos):
        if progress_label:
            progress_label.config(
                text=f"已處理 {processed_videos} / {total_videos}"
            )
            progress_label.update_idletasks()
            progress_win.update()

    # 生成首頁
    index_file_name = f"{os.path.basename(folder)}.html"

    try:
        processed_videos = generate_index_html(
            SOURCE_ROOT,
            folder,
            cover_folder,
            html_folder,
            index_file_name,
            total_videos,
            processed_videos,
            ffmpeg_exe,
            cancel_state,
            update_progress,
        )
    finally:
        if progress_win:
            progress_win.destroy()

    open_index(html_folder, index_file_name)


if __name__ == "__main__":
    main()
