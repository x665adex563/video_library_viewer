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
import sys

# --------------------
# ffmpeg 路徑設定
# --------------------
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# 指定 ffmpeg.exe 路徑
FFMPEG_EXE = os.path.join(APP_DIR, "ffmpeg", "bin", "ffmpeg.exe")

# --------------------
# 設定 / 常數
# --------------------
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".avi", ".mov")

# --------------------
# 取消用例外
# --------------------
class CancelGeneration(Exception):
    pass

# --------------------
# 進度狀態
# --------------------
CANCEL_REQUESTED = False

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
# 掃描是否有封面圖
# --------------------
def scan_missing_covers(SOURCE_ROOT, cover_folder):
    """
    掃描所有影片，回傳缺少封面圖的影片路徑清單
    """
    missing = []

    for root, _, files in os.walk(SOURCE_ROOT):
        for f in files:
            if f.lower().endswith(VIDEO_EXTENSIONS):
                cover_path = os.path.join(cover_folder, f"{f}.jpg")
                if not os.path.exists(cover_path):
                    missing.append(os.path.join(root, f))

    return missing

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
def create_progress_window(root, total, on_cancel):
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
        global CANCEL_REQUESTED
        CANCEL_REQUESTED = True

    btn = Button(
        win,
        text="取消並開啟網頁",
        command=cancel
    )
    btn.pack(pady=5)

    return win, label



# --------------------
# 封面圖生成
# --------------------
def generate_video_cover(
    video_path, cover_path, total_videos, allow_generate_cover
):
    if CANCEL_REQUESTED:
        return

    if not allow_generate_cover or CANCEL_REQUESTED:
        # 直接略過封面生成，但 HTML 還是會生成
        return

    if os.path.exists(cover_path):
        return

    os.makedirs(os.path.dirname(cover_path), exist_ok=True)

    capture_time = COVER_CAPTURE_TIME

    # 自動判斷 ffmpeg 路徑
    if os.path.exists(FFMPEG_EXE):
        ffmpeg_cmd = FFMPEG_EXE
    else:
        ffmpeg_cmd = "ffmpeg"

    subprocess.run(
        [
            ffmpeg_cmd,
            "-ss", str(capture_time),
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
# 影片播放頁
# --------------------
def generate_video_page(
    video_path,
    html_folder,
    cover_folder,
    total_videos,
    processed_videos,
    allow_generate_cover,
):

    video_name = os.path.basename(video_path)
    video_base = os.path.splitext(video_name)[0]
    html_file = os.path.join(html_folder, f"{video_name}.html")

    # 確保封面資料夾存在
    os.makedirs(cover_folder, exist_ok=True)

    # 預設封面（黑底）
    default_cover = os.path.join(cover_folder, "default.jpg")
    if not os.path.exists(default_cover):
        from PIL import Image
        img = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT), color=(0, 0, 0))
        img.save(default_cover)

    # 封面路徑
    cover_path = os.path.join(cover_folder, f"{video_name}.jpg")

    if not allow_generate_cover or CANCEL_REQUESTED:
        # 不生成封面，改用預設封面
        cover_path = default_cover
    else:
        # 生成封面
        generate_video_cover(
            video_path, cover_path, total_videos, allow_generate_cover
        )

    rel_video_path = relative_path(html_file, video_path)
    rel_cover_path = relative_path(html_file, cover_path)

    # ---------- 右側清單 ----------
    folder = os.path.dirname(video_path)
    folder_videos = sorted(
        [f for f in os.listdir(folder) if f.lower().endswith(VIDEO_EXTENSIONS)],
        key=natural_sort_key
    )

    video_list = []
    for vid in folder_videos:
        vid_base = os.path.splitext(vid)[0]
        vid_html = os.path.join(html_folder, f"{vid}.html")
        video_list.append({
            "name": vid_base,
            "html": relative_path(html_file, vid_html)
        })

    video_list_json = json.dumps(video_list, ensure_ascii=False)

    parent_folder = os.path.dirname(video_path)
    parent_html = folder_to_html_name(SOURCE_ROOT, parent_folder)
    rel_parent_html = relative_path(html_file, os.path.join(html_folder, parent_html))

    # ---------- 寫入 HTML ----------
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{video_name}</title>
<style>
body {{ margin:0; background:#000; color:#fff; font-family:sans-serif; height:100vh; overflow:hidden; }}
#back {{ position:fixed; top:20px; left:20px; z-index:2000; }}
#back a {{ padding:12px 20px; background:#000; color:#fff; text-decoration:none; border-radius:8px; font-size:18px; opacity:0.7; }}
#back a:hover {{ opacity:1; background:#222; }}
#player-wrapper {{ position:relative; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; }}
#player-wrapper.fake-fullscreen {{ position:fixed; inset:0; background:black; z-index:9999; display:flex; justify-content:center; align-items:center; }}
#player-wrapper.fake-fullscreen video {{ width: auto; height: 100%; max-width: 100vw; max-height: 100vh; object-fit: contain; z-index: 1; }}
#player-wrapper.fake-fullscreen #controls {{ position:absolute; bottom:20px; left:50%; transform:translateX(-50%); width:90vw; opacity:0; transition:opacity 0.3s; z-index:10; }}
#player-wrapper.fake-fullscreen #video-title {{ display: none; }}
video {{ max-width:90vw; max-height:80vh; cursor:pointer; }}
#controls {{ position:relative; width:90vw; margin-top:10px; display:flex; align-items:center; gap:10px; z-index:10; }}
#progress {{ border:none; outline:none; box-shadow:none; width:100%; appearance:none; -webkit-appearance:none; background:transparent; cursor:pointer; }}
#progress::-webkit-slider-runnable-track {{ height:15px; border-radius:8px; background: linear-gradient(to right, #4aa3ff 0%, #4aa3ff var(--played,0%), #444 var(--played,0%), #444 100%); }}
#progress::-webkit-slider-thumb {{ -webkit-appearance:none; height:18px; width:18px; border-radius:50%; background:#fff; margin-top:-1.5px; cursor:pointer; }}
#volume-container {{ display:flex; align-items:center; }}
#volume-slider {{ width:80px; }}
#fullscreen-btn {{ font-size:20px; cursor:pointer; }}
#video-title {{ margin-top:10px; text-align:center; }}
#video-list {{
    position:fixed;
    top:0;
    right:0;
    width:12vw;
    height:100%;
    background:rgba(0,0,0,0.5);
    overflow-y:auto;
    padding:10px;
    display:flex;
    flex-direction:column;
    gap:5px;
    opacity:0;
    transition:opacity 0.3s;
    z-index:10000;
}}
#video-list a {{
    color:#fff;
    text-decoration:none;
    padding:6px 8px;
    border-radius:4px;
    background:#222;
    opacity:0.8;
}}
#video-list a:hover {{ background:#4aa3ff; }}
</style>
</head>
<body>

<!-- 返回上一層資料夾 -->
<div id="back"><a href="javascript:history.back()">← 返回</a></div>

<div id="player-wrapper">
  <video id="video" src="{rel_video_path}" autoplay preload="metadata"></video>
  <div id="video-title">{video_name}</div>
  <div id="controls">
    <span id="current-time">0:00</span> / <span id="total-time">0:00</span>
    <input type="range" id="progress" min="0" value="0">
    <div id="volume-container">
      <input type="range" id="volume-slider" min="0" max="1" step="0.01" value="1">
      <span id="volume-icon">🔊</span>
    </div>
    <span id="fullscreen-btn">⛶</span>
  </div>
</div>

<div id="video-list"></div>

<script>
const video = document.getElementById("video");
const progress = document.getElementById("progress");
const currentTimeEl = document.getElementById("current-time");
const totalTimeEl = document.getElementById("total-time");
const volumeSlider = document.getElementById("volume-slider");
const volumeIcon = document.getElementById("volume-icon");
const fullscreenBtn = document.getElementById("fullscreen-btn");
const playerWrapper = document.getElementById("player-wrapper");
const videoList = {video_list_json};
const currentVideo = "{video_base}";
const listDiv = document.getElementById("video-list");
let controlsTimer=null;
let isFakeFullscreen=false;
let mouseTimer = null;

function hideCursor() {{
    if (isFakeFullscreen) {{
        video.style.cursor = "none";
        document.body.style.cursor = "none";
    }}
}}

function showCursor() {{
    video.style.cursor = "default";
    playerWrapper.style.cursor = "default";
    if (mouseTimer) clearTimeout(mouseTimer);
    if (isFakeFullscreen) {{
        mouseTimer = setTimeout(hideCursor, 500); // 500ms 後隱藏滑鼠
    }}
}}

// 監聽滑鼠移動
document.addEventListener("mousemove", (e) => {{
    if (!isFakeFullscreen) return;
    showCursor();
    // 控制列顯示
    showControls(500);
}});

videoList.forEach(v => {{
    if (v.name === currentVideo) return;
    const a = document.createElement("a");
    a.href = v.html;
    a.textContent = v.name;
    listDiv.appendChild(a);
}});

// 滑鼠靠右顯示
document.addEventListener("mousemove", e => {{
    listDiv.style.opacity = (e.clientX > window.innerWidth * 0.88) ? 1 : 0;
}});

// 滑鼠靠右顯示清單（全螢幕專用）
document.addEventListener("mousemove", e => {{
    if (!isFakeFullscreen) return; // 只在全螢幕

    if (e.clientX > window.innerWidth * 0.88) {{
        listDiv.style.opacity = "1";
        listDiv.style.pointerEvents = "auto"; // 可以點擊
    }} else {{
        listDiv.style.opacity = "0";
        listDiv.style.pointerEvents = "none"; // 不可點擊
    }}

    // 同時顯示控制列
    showControls(500);
}});

function showControls(duration=500){{
    const controls=document.getElementById("controls");
    controls.style.opacity=1;
    if(controlsTimer) clearTimeout(controlsTimer);
    controlsTimer=setTimeout(()=>{{ if(playerWrapper.classList.contains("fake-fullscreen")) controls.style.opacity=0; }}, duration);
}}
function hideControls(){{ document.getElementById("controls").style.opacity=0; }}
function formatTime(sec){{ const h = Math.floor(sec / 3600); const m = Math.floor((sec % 3600) / 60); const s = Math.floor(sec % 60); return h>0?`${{h}}:${{m.toString().padStart(2,"0")}}:${{s.toString().padStart(2,"0")}}`:`${{m}}:${{s.toString().padStart(2,"0")}}`; }}
function updateVolumeUI(){{ volumeSlider.value=video.volume; volumeIcon.textContent=video.volume===0?"🔇":"🔊"; showControls(500); }}

video.addEventListener("loadedmetadata", ()=>{{ totalTimeEl.textContent=formatTime(video.duration); progress.max=video.duration; }});
video.addEventListener("timeupdate", ()=>{{ currentTimeEl.textContent=formatTime(video.currentTime); progress.value=video.currentTime; progress.style.setProperty("--played",(video.currentTime/video.duration*100)+"%"); }});
progress.addEventListener("input", ()=>{{ video.currentTime=parseFloat(progress.value); progress.style.setProperty("--played",(video.currentTime/video.duration*100)+"%"); }});

volumeSlider.addEventListener("input", ()=>{{ video.volume=parseFloat(volumeSlider.value); updateVolumeUI(); }});
video.addEventListener("wheel", e=>{{ e.preventDefault(); const delta=e.deltaY<0?0.05:-0.05; video.volume=Math.min(1,Math.max(0,video.volume+delta)); updateVolumeUI(); }}, {{passive:false}});
video.setAttribute("tabindex", "-1");

function toggleFullscreen(){{
    if(!document.fullscreenElement){{
        document.documentElement.requestFullscreen();
        playerWrapper.classList.add("fake-fullscreen");
        isFakeFullscreen=true;
        showControls(500);
    }} else {{
        document.exitFullscreen();
        playerWrapper.classList.remove("fake-fullscreen");
        isFakeFullscreen=false;
        hideControls();
    }}
}}
fullscreenBtn.addEventListener("click", toggleFullscreen);
document.addEventListener("keydown", e=>{{ if(e.key==="Escape" && isFakeFullscreen) toggleFullscreen(); }});
document.addEventListener("mousemove", ()=>{{ showControls(); }});
document.addEventListener("keydown", e => {{
    const blockKeys = ["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"," "];

    if (blockKeys.includes(e.key)) {{
        e.preventDefault();
        e.stopPropagation();
    }}

    switch (e.key) {{
        case " ":
            video.paused ? video.play() : video.pause();
            showControls(500);
            break;

        case "ArrowLeft":
            video.currentTime = Math.max(0, video.currentTime - 3);
            showControls(500);
            break;

        case "ArrowRight":
            video.currentTime = Math.min(video.duration, video.currentTime + 3);
            showControls(500);
            break;

        case "ArrowUp":
            video.volume = Math.min(1, video.volume + 0.05);
            updateVolumeUI();
            break;

        case "ArrowDown":
            video.volume = Math.max(0, video.volume - 0.05);
            updateVolumeUI();
            break;

        case "Enter":
            toggleFullscreen();
            break;
    }}
}});

video.addEventListener("click", ()=>{{ video.paused?video.play():video.pause(); }});
</script>

</body>
</html>
""")

    processed_videos += 1

    if progress_label:
        progress_label.config(
            text=f"已處理 {processed_videos} / {total_videos}"
        )
        progress_label.update_idletasks()
        progress_win.update()

    return html_file, cover_path, processed_videos


# --------------------
# 章節頁（使用封面圖）
# --------------------
def generate_chapter_html(
    folder,
    html_folder,
    parent_index_html,
    viewer_folder,
    total_videos,
    processed_videos,
    allow_generate_cover,
):
    subdirs = sorted(
        [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))],
        key=natural_sort_key
    )
    videos = sorted(
        [f for f in os.listdir(folder) if f.lower().endswith(VIDEO_EXTENSIONS)],
        key=natural_sort_key
    )

    folder_name = os.path.basename(folder)
    html_name = folder_to_html_name(SOURCE_ROOT, folder)
    html_file = os.path.join(html_folder, html_name)

    cover_folder = os.path.join(viewer_folder, "covers")
    os.makedirs(cover_folder, exist_ok=True)

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{folder_name}</title>
<style>
body {{ background:#000; color:#fff; font-family:sans-serif; }}
ul {{ list-style:none; padding:20px; display:grid; grid-template-columns:repeat(7,1fr); gap:15px; justify-items:center; }}
li {{ background:#111; border-radius:8px; overflow:hidden; text-align:center; }}
.video-thumb {{ width:100%; aspect-ratio:16/9; object-fit:cover; background:#000; }}
.folder-thumb {{ width:100%; aspect-ratio:16/9; display:flex; align-items:center; justify-content:center; font-size:36px; background:#111; color:#fff; }}
.item-name {{ margin:6px 0; font-size:14px; word-break:break-word; color:#fff; }}
#back {{ position:fixed; top:20px; left:20px; z-index:1000; }}
#back a {{ display:inline-block; padding:20px 20px; background:#000; color:#fff; text-decoration:none; border-radius:8px; font-size:20px; opacity:0.6; }}
#back:hover a {{ opacity:1; background:#222; }}
</style>
</head>
<body>
""")
        if parent_index_html:
            f.write('<div id="back"><a href="javascript:history.back()">← 返回</a></div>\n')

        f.write('<ul>\n')

        # 子資料夾
        for d in subdirs:
            d_path = os.path.join(folder, d)
            child_html = folder_to_html_name(SOURCE_ROOT, d_path)

            chapter_html, processed_videos = generate_chapter_html(
                d_path,
                html_folder,
                html_file,
                viewer_folder,
                total_videos,
                processed_videos,
                allow_generate_cover,
            )

            f.write(f"""<li>
  <a href="{child_html}">
    <div class="folder-thumb">📁</div>
    <div class="item-name">{d}</div>
  </a>
</li>\n""")

        # 影片
        for vid in videos:
            vid_path = os.path.join(folder, vid)
            video_page, cover_path, processed_videos = generate_video_page(
                vid_path,
                html_folder,
                cover_folder,
                total_videos,
                processed_videos,
                allow_generate_cover,
            )

            f.write(f"""<li>
  <a href="{relative_path(html_file, video_page)}">
    <img class="video-thumb" src="{relative_path(html_file, cover_path)}">
    <div class="item-name">{vid}</div>
  </a>
</li>\n""")

        f.write('</ul>\n</body></html>\n')

    return html_file, processed_videos


# --------------------
# 首頁
# --------------------
def generate_index_html(
    folder,
    viewer_folder,
    html_folder,
    index_name,
    total_videos,
    processed_videos,
    allow_generate_cover,
):

    index_file_name = f"{os.path.basename(folder)}.html"

    html_file = os.path.join(html_folder, index_name)
    folder_name = os.path.basename(folder)

    subdirs = sorted(
        [d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))],
        key=natural_sort_key
    )
    videos = sorted(
        [f for f in os.listdir(folder) if f.lower().endswith(VIDEO_EXTENSIONS)],
        key=natural_sort_key
    )

    with open(html_file, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{folder_name}</title>
<style>
body {{ background:#000; color:#fff; font-family:sans-serif; }}
ul {{ list-style:none; padding:20px; display:grid; grid-template-columns:repeat(7,1fr); gap:15px; justify-items:center; }}
li {{ background:#111; border-radius:8px; overflow:hidden; text-align:center; }}
.video-thumb {{ width:100%; aspect-ratio:16/9; object-fit:cover; background:#000; }}
.folder-thumb {{ width:100%; aspect-ratio:16/9; display:flex; align-items:center; justify-content:center; font-size:36px; background:#111; color:#fff; }}
.item-name {{ margin:6px 0; font-size:14px; color:#fff; }}
</style>
</head>
<body>
<ul>
""")

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
            chapter_html, processed_videos = generate_chapter_html(
                d_path,
                html_folder,
                html_file,
                viewer_folder,
                total_videos,
                processed_videos,
                allow_generate_cover,
            )

        # 影片
        for v in videos:
            v_path = os.path.join(folder, v)
            page, cover_path, processed_videos = generate_video_page(
                v_path,
                html_folder,
                os.path.join(viewer_folder, "covers"),
                total_videos,
                processed_videos,
                allow_generate_cover,
            )

            f.write(f"""<li>
  <a href="{relative_path(html_file, page)}">
    <img class="video-thumb" src="{relative_path(html_file, cover_path)}">
    <div class="item-name">{v}</div>
  </a>
</li>\n""")

        f.write("</ul></body></html>")

    return html_file, processed_videos


# --------------------
# 主程式
# --------------------
def main():
    global SOURCE_ROOT, progress_label, progress_win

    allow_generate_cover = True
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

    missing_covers = scan_missing_covers(SOURCE_ROOT, cover_folder)

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
            on_cancel=open_index
        )

    else:
        progress_win = None
        progress_label = None

    # 生成首頁
    index_file_name = f"{os.path.basename(folder)}.html"

    try:
        final_index, processed_videos = generate_index_html(
            folder,
            viewer_folder,
            html_folder,
            index_file_name,
            total_videos,
            processed_videos,
            allow_generate_cover,
        )
    except CancelGeneration:
        pass
    finally:
        if progress_win:
            progress_win.destroy()

    open_index(html_folder, index_file_name)


if __name__ == "__main__":
    main()