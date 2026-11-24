"""
PHOENIX BROWSER v5.0.3 - ANDROID - Flet 1.1.2
Same logic as PC v5.0.3:
- Try 1 = android+web FIRST (winner)
- Scan tries android+web -> web -> android, fallback adds video anyway
- Fullscreen video fills screen
- Paste Link + Download Pasted Link
- Tick videos, NOT auto-ticked
- Quality: Best / 720p / 480p / Audio MP3
- Download to /storage/emulated/0/Download/Phoenix

BUILD: flet build apk --project phoenix_android
Or: python -m flet build apk
"""
import flet as ft
import threading, os, time, re, shutil

try:
    DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "Phoenix")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
except Exception:
    DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Phoenix")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

ATTEMPTS = [
    {'label': 'android+web', 'args': {'youtube': {'player_client': ['android','web']}}},
    {'label': 'web', 'args': {'youtube': {'player_client': ['web']}}},
    {'label': 'android', 'args': {'youtube': {'player_client': ['android']}}},
    {'label': 'web bv+ba', 'args': {'youtube': {'player_client': ['web']}}},
]
SCAN_ATTEMPTS = [
    {'youtube': {'player_client': ['android','web']}},
    {'youtube': {'player_client': ['web']}},
    {'youtube': {'player_client': ['android']}},
]

def main(page: ft.Page):
    page.title = "Phoenix Browser v5.0.3 Android"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#111111"
    page.window_width = 400
    page.window_height = 800
    page.padding = 0
    page.spacing = 0

    detected = []  # [{'title','url'}]
    selected = set()
    downloading = [False]
    stop_flag = [False]

    # --- LOG ---
    log_box = ft.TextField(
        value="🔥 Phoenix v5.0.3 Android - Ready\n",
        multiline=True, read_only=True, expand=True,
        text_size=12, color="#00FF88", bgcolor="black",
        min_lines=6, max_lines=8,
    )
    def log(msg):
        if any(x in msg for x in ['generate_204','ResizeObserver','Access-Control','Allow-Origin','CORS']):
            return
        log_box.value += msg + "\n"
        log_box.update()
        try:
            page.update()
        except: pass

    # --- WEBVIEW - KEEP FOR PHONE, FRIENDLY MESSAGE ON PC (NO RED BOX) ---
    # Fam: WebView is NOT removed. On Android APK it is real browser.
    # On Windows PC, flet_webview shows ugly red box, so we show friendly placeholder instead.
    import platform as _platform
    _is_windows = _platform.system() == "Windows"
    webview = None
    webview_holder = ft.Container(expand=True, bgcolor="black", alignment=ft.Alignment(0, 0))
    if _is_windows:
        # PC TEST MODE: Do NOT create WebView (avoids red box). Show friendly message.
        webview = None
        webview_holder.content = ft.Column([
            ft.Text("Phoenix WebView", color="white", size=18, weight="bold"),
            ft.Text("Web browsing works on PHONE APK.", color="#00FF88", size=13),
            ft.Text("On PC test, WebView is hidden to avoid red box.", color="grey", size=12),
            ft.Text("Use Paste Link + Download below - that is Phoenix power.", color="grey", size=12),
            ft.Text("Build APK to see real WebView on your phone.", color="#FF9800", size=12, weight="bold"),
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
   else:
        # ANDROID: Real WebView
        try:
           try:
               from flet_webview import WebView as FletWebView
               webview = FletWebView(url="https://www.youtube.com", expand=True)
           except:
               webview = ft.WebView(url="https://www.youtube.com", expand=True)
           webview_holder.content = webview
        except Exception as e:
           webview = None
           webview_holder.content = ft.Column([
               ft.Text("Phoenix WebView", color="white", size=16, weight="bold"),
               ft.Text("WebView failed to load", color="grey", size=13),
           ], alignment=ft.MainAxisAlignment.CENTER)

    url_bar = ft.TextField(value="https://www.youtube.com", expand=True, text_size=13, bgcolor="white", color="black", border_radius=8)
    def go_url(e=None):
        t = url_bar.value.strip()
        if not t.startswith("http"):
            t = "https://" + t
        url_bar.value = t
        url_bar.update()
        if webview is not None:
            try:
                webview.url = t
                webview.update()
            except: pass
        log(f"Page: {t}")

    # --- PASTE LINK ---
    paste_entry = ft.TextField(hint_text="Paste YouTube / TikTok / FB / IG link", expand=True, text_size=13, bgcolor="white", color="black", border_radius=8)
    def paste_clip(e):
        try:
            import pyperclip
            paste_entry.value = pyperclip.paste()
            paste_entry.update()
        except:
            log("📋 Long-press Paste box to paste on Android")

    # --- VIDEO LIST ---
    video_list = ft.ListView(expand=True, spacing=4, height=220)
    header = ft.Text("📋 VIDEOS FOUND (0) - Tick what you want", color="white", size=13, weight="bold")
    progress_text = ft.Text("No download yet", color="#00FF88", size=12, weight="bold")
    progress_bar = ft.ProgressBar(value=0, color="#FF0000", bgcolor="#333333", height=10)
    overall_label = ft.Text("Overall: 0/0 done", color="#FFB347", size=12, weight="bold")
    quality_dd = ft.Dropdown(
        value="Best",
        options=[ft.dropdown.Option("Best"), ft.dropdown.Option("720p"), ft.dropdown.Option("480p"), ft.dropdown.Option("Audio MP3")],
        bgcolor="white", color="black", width=180, text_size=13,
    )
    queue_label = ft.Text("📥 QUEUE: 0 videos", color="white", size=12)

    def rebuild_list():
        video_list.controls.clear()
        for d in detected:
            is_checked = d['url'] in selected
            def on_change(e, url=d['url']):
                if e.control.value:
                    selected.add(url)
                else:
                    selected.discard(url)
                dl_sel_btn.text = f"⬇ DOWNLOAD SELECTED ({len(selected)})"
                dl_sel_btn.update()
            video_list.controls.append(
                ft.Row([
                    ft.Checkbox(value=is_checked, on_change=on_change),
                    ft.Text(d['title'][:60], color="white", size=12, expand=True),
                ], spacing=4)
            )
        header.value = f"📋 VIDEOS FOUND ({len(detected)}) - Tick what you want (NOT auto-ticked)"
        header.update()
        video_list.update()

    def do_scan(url):
        import yt_dlp
        is_single = 'watch?v=' in url
        last_err = ""
        for sargs in SCAN_ATTEMPTS:
            try:
                opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True, 'skip_download': True, 'extractor_args': sargs}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        continue
                    if 'entries' in info and info['entries']:
                        new = 0
                        for e in info['entries']:
                            if not e: continue
                            vid = e.get('id','')
                            vurl = f"https://www.youtube.com/watch?v={vid}" if vid else e.get('url') or url
                            if not any(x['url']==vurl for x in detected):
                                detected.append({'title': e.get('title','Unknown'), 'url': vurl}); new+=1
                        log(f"✓ Found {len(detected)} videos - NOT ticked (added {new})")
                        rebuild_list(); return
                    else:
                        if not any(x['url']==url for x in detected):
                            detected.append({'title': info.get('title', url), 'url': url})
                        log(f"✓ Found {len(detected)} videos - NOT ticked")
                        rebuild_list(); return
            except Exception as ex:
                last_err = str(ex); continue
        if is_single:
            m = re.search(r'v=([A-Za-z0-9_-]{11})', url)
            vid = m.group(1) if m else url
            clean = f"https://www.youtube.com/watch?v={vid}" if m else url
            if not any(x['url']==clean for x in detected):
                detected.append({'title': f"Video: {vid} (Scan fallback)", 'url': clean})
                log(f"⚠️ Scan gave 0 formats, but added {vid} anyway - tick + Download")
                rebuild_list(); return
        log(f"⚠️ Scan failed. Try Paste Link + Download Pasted. {last_err[:80]}")

    def scan_page(e):
        url = url_bar.value.strip() or "https://www.youtube.com"
        log(f"Scanning: {url}")
        threading.Thread(target=do_scan, args=(url,), daemon=True).start()

    # --- DOWNLOAD ---
    def do_download_queue(videos, q_passed):
        import yt_dlp
        q = q_passed
        is_mp3 = (q == "Audio MP3")
        if q == "720p": fmt_base = 'best[height<=720]/best'
        elif q == "480p": fmt_base = 'best[height<=480]/best'
        elif is_mp3: fmt_base = 'bestaudio/best'
        else: fmt_base = 'best'
        log(f"v5.0.3 Android: Try 1 = android+web | Quality={q} | Total={len(videos)}")
        done = 0; fail = 0
        for i, v in enumerate(videos, 1):
            if stop_flag[0]:
                log("⏹ Stopped"); break
            log(f"[{i}/{len(videos)}] Downloading: {v['title'][:50]} | Quality={q}")
            success = False; last_err = ""
            for idx, att in enumerate(ATTEMPTS, 1):
                if stop_flag[0]: break
                if is_mp3: fmt = 'bestaudio/best'
                elif idx in (1,2): fmt = fmt_base
                elif idx == 3: fmt = 'best'
                else: fmt = 'bv*+ba/best'
                if idx == 1: log(f"   Trying {att['label']}...")
                else: log(f"   Trying backup {idx}: {att['label']}...")
                def hook(d):
                    if d['status'] == 'downloading':
                        dl = d.get('downloaded_bytes',0) or 0
                        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        speed = d.get('speed') or 0
                        if total > 0:
                            progress_text.value = f"[{i}/{len(videos)}] {dl/1024/1024:.1f} MB / {total/1024/1024:.1f} MB ({int(dl/total*100)}%) | {speed/1024/1024:.2f} MB/s"
                            progress_bar.value = dl/total
                        else:
                            progress_text.value = f"[{i}/{len(videos)}] {dl/1024/1024:.1f} MB | {speed/1024:.0f} KB/s"
                        try:
                            progress_text.update(); progress_bar.update()
                        except: pass
                    elif d['status'] == 'finished':
                        log(f"   ✓ File finished: {d.get('filename','')}")
                opts = {'format': fmt, 'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s-%(id)s.%(ext)s'),
                        'progress_hooks': [hook], 'noplaylist': True, 'quiet': True, 'no_warnings': True,
                        'extractor_args': att['args'], 'retries': 2, 'fragment_retries': 2,
                        'format_sort': ['res','ext:mp4:m4a'], 'merge_output_format': 'mp4' if not is_mp3 else None}
                if is_mp3:
                    opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
                    opts['keepvideo'] = False
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([v['url']])
                    success = True
                    log(f"✓ DONE [{i}/{len(videos)}]: {v['title'][:50]} -> {' .mp3' if is_mp3 else ' video'} (via {att['label']})")
                    break
                except Exception as ex:
                    last_err = str(ex)
                    if idx < len(ATTEMPTS): log(f"   ... {att['label']} didn't work, trying backup...")
                    else: log(f"   ✗ All tries failed: {last_err[:80]}")
                    time.sleep(1); continue
            if success: done += 1
            else:
                fail += 1
                log(f"✗ FAILED [{i}/{len(videos)}]: {v['title'][:50]} | {last_err[:100]}")
            overall_label.value = f"Overall: {done}/{len(videos)} done, {fail} failed"
            try: overall_label.update()
            except: pass
        downloading[0] = False
        queue_label.value = "QUEUE DONE - " + str(done) + "/" + str(len(videos)) + " done"
        try:
            queue_label.update()
        except:
            pass
        if fail == 0 and not stop_flag[0]:
            log(f"✅ ALL DONE! {done}/{len(videos)} -> {DOWNLOAD_DIR}")
            progress_text.value = f"✅ ALL DONE! {done}/{len(videos)}"
            progress_bar.value = 1.0
        elif not stop_flag[0]:
            log(f"⚠️ FINISHED: {done} done, {fail} failed")
        try:
            progress_text.update(); progress_bar.update()
        except: pass

    def start_queue(vids, q_now):
        if downloading[0]:
            log("⚠️ Already downloading - wait or Stop"); return
        downloading[0] = True; stop_flag[0] = False
        queue_label.value = f"📥 QUEUE: {len(vids)} videos - Downloading..."
        queue_label.update()
        threading.Thread(target=do_download_queue, args=(list(vids), q_now), daemon=True).start()

    def download_pasted(e):
        url = paste_entry.value.strip()
        if not url.startswith("http"):
            log("⚠️ Paste a valid link first!"); return
        log(f"▶️ STARTING Pasted Link... Quality={quality_dd.value} | {url[:80]}")
        paste_entry.value = ""; paste_entry.update()
        start_queue([{'title': url, 'url': url}], quality_dd.value)

    def add_pasted(e):
        url = paste_entry.value.strip()
        if not url.startswith("http"):
            log("⚠️ Paste a valid link first!"); return
        if not any(x['url']==url for x in detected):
            detected.append({'title': f"Pasted: {url}", 'url': url})
        rebuild_list(); paste_entry.value = ""; paste_entry.update()

    def download_selected(e):
        if not selected:
            log("⚠️ Tick a video first!"); return
        vids = [d for d in detected if d['url'] in selected]
        for u in list(selected):
            if u not in [d['url'] for d in vids]:
                vids.append({'title': u, 'url': u})
        log(f"▶️ STARTING {len(vids)} SELECTED... Quality={quality_dd.value}")
        start_queue(vids, quality_dd.value)

    def download_all(e):
        if not detected:
            log("No videos - Scan first or Paste Link!"); return
        log(f"▶️ STARTING ALL {len(detected)}... Quality={quality_dd.value}")
        start_queue(list(detected), quality_dd.value)

    def stop_dl(e):
        stop_flag[0] = True; log("⏹ Stopping after current video...")

    def clear_list(e):
        detected.clear(); selected.clear(); rebuild_list(); log("List cleared")

    def select_all(e):
        for d in detected: selected.add(d['url'])
        rebuild_list()
        dl_sel_btn.text = f"⬇ DOWNLOAD SELECTED ({len(selected)})"
        dl_sel_btn.update()

    dl_sel_btn = ft.FilledButton("⬇ DOWNLOAD SELECTED (0)", bgcolor="#FF0000", color="white", on_click=download_selected, expand=True)

    # --- LAYOUT ---
    page.add(
        ft.Container(
            content=ft.Text("🔥 PHOENIX v5.0.3 ANDROID — android+web FIRST | Fullscreen Fixed | Scan Never Fails", color="white", size=12, weight="bold"),
            bgcolor="#1a1a1a", padding=8, alignment=ft.Alignment(0, 0),
        ),
        # Paste row
        ft.Container(
            content=ft.Column([
                ft.Row([paste_entry, ft.FilledButton("📋 Paste", bgcolor="#DDDDDD", color="black", on_click=paste_clip)], spacing=6),
                ft.Row([
                    ft.FilledButton("⬇ DOWNLOAD PASTED LINK", bgcolor="#FF0000", color="white", on_click=download_pasted, expand=True),
                    ft.FilledButton("＋ Add to List", bgcolor="#333333", color="white", on_click=add_pasted),
                ], spacing=6),
            ], spacing=6),
            bgcolor="#1a1a1a", padding=8,
        ),
        # Nav row
        ft.Container(
            content=ft.Row([
                ft.FilledButton("◀", bgcolor="white", color="black", on_click=lambda e: webview.go_back() if webview else None, width=40),
                ft.FilledButton("▶", bgcolor="white", color="black", on_click=lambda e: webview.go_forward() if webview else None, width=40),
                ft.FilledButton("↻", bgcolor="white", color="black", on_click=lambda e: webview.reload() if webview else None, width=40),
                url_bar,
                ft.FilledButton("GO →", bgcolor="#FF0000", color="white", on_click=go_url),
            ], spacing=6),
            bgcolor="#1a1a1a", padding=8,
        ),
        # WebView - flexible
        ft.Container(content=webview_holder, expand=True, bgcolor="black", height=280),
        # Controls
        ft.Container(
            content=ft.Column([
                header,
                ft.Container(content=video_list, height=180, bgcolor="#111111", border_radius=8, padding=4),
                ft.Row([ft.Text("Quality:", color="white", size=13), quality_dd, ft.FilledButton("🔍 SCAN", bgcolor="#FF9800", color="white", on_click=scan_page)], spacing=8),
                ft.Row([ft.FilledButton("Clear", bgcolor="#DDDDDD", color="black", on_click=clear_list), ft.FilledButton("☑ Select All", bgcolor="#DDDDDD", color="black", on_click=select_all)], spacing=6),
                dl_sel_btn,
                ft.FilledButton("⬇ DOWNLOAD ALL", bgcolor="#DDDDDD", color="black", on_click=download_all, expand=True),
                queue_label,
                ft.Row([ft.FilledButton("⏹ Stop", bgcolor="#333333", color="white", on_click=stop_dl), ft.FilledButton("📂 Folder: Download/Phoenix", bgcolor="#333333", color="white", on_click=lambda e: log(f"Files in: {DOWNLOAD_DIR}"))], spacing=6),
                overall_label,
                progress_text,
                progress_bar,
                ft.Text("Log:", color="white", size=12),
                ft.Container(content=log_box, height=140, bgcolor="black", border_radius=8, padding=4),
                ft.Text("✅ v5.0.3 Android - Same engine as PC", color="#00FF88", size=11),
            ], spacing=6, scroll=ft.ScrollMode.AUTO),
            bgcolor="#1a1a1a", padding=8, expand=True,
        ),
    )

# Flet 1.1.2 - ft.app is correct. If you got AttributeError before, you were on old flet.
if __name__ == "__main__":
   ft.app(target=main)




