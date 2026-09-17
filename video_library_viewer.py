#網頁看影片v2(預覽圖)

import os
import webbrowser
from tkinter import Tk, filedialog
import re
import subprocess
from urllib.parse import quote
import json
from tkinter import messagebox
from tkinter import Label, Button
from tkinter import Toplevel
from pathlib import Path
from cover_generator import ensure_default_cover, generate_video_cover


# --------------------
# 設定 / 常數
# --------------------
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".avi", ".mov")


# 封面圖
# 封面圖（Level 1：固定時間點）
COVER_CAPTURE_TIME = 80   # 全部影片一律抓 80 秒
COVER_WIDTH = 320
COVER_HEIGHT = 180

# --------------------
# 工具
# --------------------
def natural_sort_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

def get_videos(folder):
    return sorted(
        [f for f in os.listdir(folder) if f.lower().endswith(VIDEO_EXTENSIONS)],
        key=natural_sort_key
    )

def get_subdirectories(folder):
    return sorted(
        [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))],
        key=natural_sort_key
    )

def get_all_videos(SOURCE_ROOT):
    videos = []

    for root, _, files in os.walk(SOURCE_ROOT):
        for f in files:
            if f.lower().endswith(VIDEO_EXTENSIONS):
                videos.append(os.path.join(root, f))

    return videos

def relative_path(from_path, to_path):
    from_path_abs = os.path.abspath(from_path)
    to_path_abs = os.path.abspath(to_path)
    from_drive = os.path.splitdrive(from_path_abs)[0].lower()
    to_drive = os.path.splitdrive(to_path_abs)[0].lower()

    if from_drive == to_drive:
        rel = os.path.relpath(to_path_abs, start=os.path.dirname(from_path_abs)).replace("\\", "/")
        return quote(rel)
    else:
        return Path(to_path_abs).as_uri()  # 或 file:/// + quote(to_path_abs)


def folder_to_html_name(SOURCE_ROOT, folder_path):
    rel = os.path.relpath(folder_path, SOURCE_ROOT)
    safe = rel.replace(os.sep, "__")
    return f"{safe}.html"

def video_to_html_name(video_name):
    return f"{video_name}.html"

# --------------------
# 首頁函式
# --------------------
def open_index(html_folder, index_file_name):
    index_path = Path(html_folder) / index_file_name

    if not index_path.exists():
        return

    url = index_path.as_uri()
    chrome = find_chrome_path()

    if chrome:
        subprocess.Popen([chrome, url])
    else:
        webbrowser.open(url)

# --------------------
# 計算要補封面圖的影片總數
# --------------------
def count_all_videos(SOURCE_ROOT):
    count = 0
    for root, _, files in os.walk(SOURCE_ROOT):
        for f in files:
            if f.lower().endswith(VIDEO_EXTENSIONS):
                count += 1
    return count

# --------------------
# 生成封面圖時的進度提示窗
# --------------------
def create_progress_window(root, total, cancel_state):
    win = Toplevel(root)
    win.title("生成中")
    win.geometry("320x120")
    win.resizable(False, False)

    label = Label(
        win,
        text=f"已處理 0 / {total}",
        font=("Segoe UI", 12)
    )
    label.pack(pady=10)

    def cancel():
        cancel_state["requested"] = True

    btn = Button(
        win,
        text="取消並開啟網頁",
        command=cancel
    )
    btn.pack(pady=5)

    return win, label

# --------------------
# 確保用Chrome開啟
# --------------------
def find_chrome_path():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

# --------------------
# 右側清單
# --------------------
def build_video_list(folder, html_folder, html_file):
    folder_videos = get_videos(folder)

    video_list = []
    for vid in folder_videos:
        vid_base = os.path.splitext(vid)[0]
        vid_html = os.path.join(html_folder, video_to_html_name(vid))
        video_list.append({
            "name": vid_base,
            "html": relative_path(html_file, vid_html)
        })

    return json.dumps(video_list, ensure_ascii=False)

def build_video_page_html(
    video_name,
    video_base,
    rel_video_path,
    video_list_json,
):
    template_path = Path(__file__).parent / "html_templates" / "video_page.html"

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("{video_name}", video_name)
    html = html.replace("{video_base}", video_base)
    html = html.replace("{rel_video_path}", rel_video_path)
    html = html.replace("{video_list_json}", video_list_json)

    return html

# --------------------
# 影片播放頁
# --------------------
def generate_video_page(
    video_path,
    html_folder,
    cover_folder,
    total_videos,
    processed_videos,
    ffmpeg_exe,
    cancel_state,
    update_progress,
):

    video_name = os.path.basename(video_path)
    video_base = os.path.splitext(video_name)[0]
    html_file = os.path.join(html_folder, video_to_html_name(video_name))

    default_cover = ensure_default_cover(cover_folder)

    # 封面路徑
    cover_path = os.path.join(cover_folder, f"{video_name}.jpg")

    if cancel_state["requested"]:
        # 不生成封面，改用預設封面
        cover_path = default_cover
    else:
        # 生成封面
        generate_video_cover(
            video_path,
            cover_path,
            ffmpeg_exe,
            cancel_state,
        )

    rel_video_path = relative_path(html_file, video_path)

    video_list_json = build_video_list(
        os.path.dirname(video_path),
        html_folder,
        html_file
    )

    # ---------- 寫入 HTML ----------
    html = build_video_page_html(
        video_name,
        video_base,
        rel_video_path,
        video_list_json,
    )

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    processed_videos += 1

    update_progress(processed_videos, total_videos)

    return html_file, cover_path, processed_videos


# --------------------
# 章節頁（使用封面圖）
# --------------------
def generate_chapter_html(
    SOURCE_ROOT,
    folder,
    html_folder,
    cover_folder,
    total_videos,
    processed_videos,
    ffmpeg_exe,
    cancel_state,
    update_progress,
):
    subdirs = get_subdirectories(folder)

    videos = get_videos(folder)

    folder_name = os.path.basename(folder)
    html_name = folder_to_html_name(SOURCE_ROOT, folder)
    html_file = os.path.join(html_folder, html_name)

    template_path = Path(__file__).parent / "html_templates" / "chapter_page.html"

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("{{TITLE}}", folder_name)

    content = ""

    # 子資料夾
    for d in subdirs:
        d_path = os.path.join(folder, d)
        child_html = folder_to_html_name(SOURCE_ROOT, d_path)

        processed_videos = generate_chapter_html(
            SOURCE_ROOT,
            d_path,
            html_folder,
            cover_folder,
            total_videos,
            processed_videos,
            ffmpeg_exe,
            cancel_state,
            update_progress,
        )

        content += f"""<li>
  <a href="{child_html}">
    <div class="folder-thumb">📁</div>
    <div class="item-name">{d}</div>
  </a>
</li>
"""

    # 影片
    for vid in videos:
        vid_path = os.path.join(folder, vid)

        video_page, cover_path, processed_videos = generate_video_page(
            vid_path,
            html_folder,
            cover_folder,
            total_videos,
            processed_videos,
            ffmpeg_exe,
            cancel_state,
            update_progress,
        )

        content += f"""<li>
  <a href="{relative_path(html_file, video_page)}">
    <img class="video-thumb" src="{relative_path(html_file, cover_path)}">
    <div class="item-name">{vid}</div>
  </a>
</li>
"""

    html = html.replace("{{CONTENT}}", content)

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    return processed_videos


# --------------------
# 首頁
# --------------------
def generate_index_html(
    SOURCE_ROOT,
    folder,
    cover_folder,
    html_folder,
    index_name,
    total_videos,
    processed_videos,
    ffmpeg_exe,
    cancel_state,
    update_progress,
):

    html_file = os.path.join(html_folder, index_name)
    folder_name = os.path.basename(folder)

    subdirs = get_subdirectories(folder)

    videos = get_videos(folder)

    template_path = Path(__file__).parent / "html_templates" / "index_page.html"

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("{folder_name}", folder_name)

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

        # 子資料夾
        for d in subdirs:
            d_path = os.path.join(folder, d)
            child_html = folder_to_html_name(SOURCE_ROOT, d_path)

            f.write(f"""<li>
  <a href="{child_html}">
    <div class="folder-thumb">📁</div>
    <div class="item-name">{d}</div>
  </a>
</li>\n""")

            # 生成章節 HTML
            processed_videos = generate_chapter_html(
                SOURCE_ROOT,
                d_path,
                html_folder,
                cover_folder,
                total_videos,
                processed_videos,
                ffmpeg_exe,
                cancel_state,
                update_progress,
            )

        # 影片
        for v in videos:
            v_path = os.path.join(folder, v)
            page, cover_path, processed_videos = generate_video_page(
                v_path,
                html_folder,
                cover_folder,
                total_videos,
                processed_videos,
                ffmpeg_exe,
                cancel_state,
                update_progress,
            )

            f.write(f"""<li>
  <a href="{relative_path(html_file, page)}">
    <img class="video-thumb" src="{relative_path(html_file, cover_path)}">
    <div class="item-name">{v}</div>
  </a>
</li>\n""")

        f.write("</ul></body></html>")

    return processed_videos
