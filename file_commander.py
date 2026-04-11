import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
import subprocess
import datetime
import json
import shutil
import urllib.request
from PIL import Image, ImageTk, ExifTags

BACKUP_DIR = os.path.expanduser("~/FILE-COMMANDER-BACKUPS")

def backup_file(path):
    """Copy file to backup folder with timestamp before any change."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name, ext = os.path.splitext(os.path.basename(path))
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"{name}_{timestamp}{ext}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    shutil.copy2(path, backup_path)
    return backup_path

current_filter = []
selected_filename = None

WINDOWS_MOUNTS = ["/media/cade/MAIN", "/media/cade/D85EE18B5EE162AC"]
WINDOWS_DEVICES = ["/dev/nvme0n1p3", "/dev/nvme0n1p4"]

def gps_to_address(gps_info):
    try:
        def to_decimal(vals):
            d, m, s = vals
            return float(d) + float(m) / 60 + float(s) / 3600

        lat = to_decimal(gps_info[2])
        lon = to_decimal(gps_info[4])
        if gps_info[1] == "S":
            lat = -lat
        if gps_info[3] == "W":
            lon = -lon

        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "FILE-COMMANDER/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return data.get("display_name", f"{lat:.5f}, {lon:.5f}")
    except Exception:
        return None

def get_metadata(path):
    try:
        stat = os.stat(path)
        size_kb = round(stat.st_size / 1024, 1)
        size_str = f"{size_kb} KB" if size_kb < 1024 else f"{round(size_kb/1024, 1)} MB"
        date_str = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        try:
            with Image.open(path) as img:
                dims = f"{img.width}x{img.height}"
        except Exception:
            dims = "—"
        return size_str, date_str, dims
    except Exception:
        return "—", "—", "—"

def load_tree(path, parent):
    for item in sorted(os.listdir(path)):
        full_path = os.path.join(path, item)
        if os.path.isfile(full_path):
            if current_filter and not any(item.lower().endswith(ext) for ext in current_filter):
                continue
        node = tree.insert(parent, "end", text=item, open=False)
        if os.path.isdir(full_path):
            tree.insert(node, "end", text="...")

def on_open(event):
    node = tree.focus()
    path = get_path(node)
    if os.path.isdir(path):
        children = tree.get_children(node)
        for child in children:
            if tree.item(child, "text") == "...":
                tree.delete(child)
                load_tree(path, node)

def on_double_click(event):
    node = tree.focus()
    values = tree.item(node, "values")
    if values:
        path = values[0]
        if os.path.isfile(path):
            # Collect all image paths from tree
            all_paths = []
            def collect(parent):
                for child in tree.get_children(parent):
                    v = tree.item(child, "values")
                    if v and os.path.isfile(v[0]):
                        all_paths.append(v[0])
                    collect(child)
            collect("")
            idx = all_paths.index(path) if path in all_paths else 0
            show_image_details(all_paths, idx)

def show_image_details(all_paths, idx):
    current = [idx]

    win = tk.Toplevel(root)
    win.geometry("900x650")

    # Navigation bar at top
    nav = tk.Frame(win)
    nav.pack(fill="x", pady=5)

    prev_btn = tk.Button(nav, text="◀ Prev", font=("Arial", 12), width=10)
    prev_btn.pack(side="left", padx=10)

    title_label = tk.Label(nav, text="", font=("Arial", 11), anchor="center")
    title_label.pack(side="left", expand=True, fill="x")

    next_btn = tk.Button(nav, text="Next ▶", font=("Arial", 12), width=10)
    next_btn.pack(side="right", padx=10)

    # Main area
    main_frame = tk.Frame(win)
    main_frame.pack(fill="both", expand=True)

    # Left — image preview
    left = tk.Frame(main_frame, width=450, bg="black")
    left.pack(side="left", fill="both", expand=True)
    left.pack_propagate(False)

    img_label = tk.Label(left, bg="black")
    img_label.pack(expand=True)

    # Right — metadata with scrollbar
    right_outer = tk.Frame(main_frame)
    right_outer.pack(side="right", fill="both", expand=True)

    canvas = tk.Canvas(right_outer)
    meta_scroll = tk.Scrollbar(right_outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=meta_scroll.set)
    meta_scroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    right = tk.Frame(canvas, padx=15, pady=15)
    canvas_window = canvas.create_window((0, 0), window=right, anchor="nw")

    right.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

    def load(i):
        path = all_paths[i]
        win.title(os.path.basename(path))
        title_label.config(text=f"{os.path.basename(path)}  ({i+1} of {len(all_paths)})")
        prev_btn.config(state="normal" if i > 0 else "disabled")
        next_btn.config(state="normal" if i < len(all_paths) - 1 else "disabled")

        # Update image
        try:
            img = Image.open(path)
            img.thumbnail((440, 580))
            photo = ImageTk.PhotoImage(img)
            img_label.config(image=photo, text="")
            img_label.image = photo
        except Exception:
            img_label.config(image="", text="Cannot preview", fg="white", font=("Arial", 12))
            img_label.image = None

        # Clear and rebuild metadata
        for w in right.winfo_children():
            w.destroy()

        tk.Label(right, text="File Info", font=("Arial", 13, "bold"), anchor="w").pack(fill="x")
        try:
            stat = os.stat(path)
            info = [
                ("Name",        os.path.basename(path)),
                ("Type",        os.path.splitext(path)[1]),
                ("Size",        f"{round(stat.st_size / 1024, 1)} KB"),
                ("Location",    os.path.dirname(path)),
                ("Created",     datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M")),
                ("Modified",    datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")),
                ("Accessed",    datetime.datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d %H:%M")),
                ("Owner",       str(stat.st_uid)),
                ("Permissions", oct(stat.st_mode)[-3:]),
            ]
            for label, val in info:
                row = tk.Frame(right)
                row.pack(fill="x", pady=2)
                tk.Label(row, text=f"{label}:", font=("Arial", 10, "bold"), width=12, anchor="w").pack(side="left")
                tk.Label(row, text=val, font=("Arial", 10), anchor="w", wraplength=280, justify="left").pack(side="left")
        except Exception as e:
            tk.Label(right, text=f"Error: {e}").pack()

        # EXIF
        try:
            img = Image.open(path)
            exif_data = img._getexif()
            if exif_data:
                tk.Label(right, text="\nEXIF Data", font=("Arial", 13, "bold"), anchor="w").pack(fill="x")
                tag_names = {v: k for k, v in ExifTags.TAGS.items()}
                want = ["Make", "Model", "DateTimeOriginal", "GPSInfo", "ExifImageWidth", "ExifImageHeight"]
                for tag in want:
                    tag_id = tag_names.get(tag)
                    if tag_id and tag_id in exif_data:
                        val = exif_data[tag_id]
                        if tag == "GPSInfo":
                            address = gps_to_address(val)
                            val = address if address else str(val)
                        row = tk.Frame(right)
                        row.pack(fill="x", pady=2)
                        tk.Label(row, text=f"{tag}:", font=("Arial", 10, "bold"), width=16, anchor="w").pack(side="left")
                        tk.Label(row, text=str(val), font=("Arial", 10), anchor="w", wraplength=240, justify="left").pack(side="left")
                row = tk.Frame(right)
                row.pack(fill="x", pady=2)
                tk.Label(row, text="Image Size:", font=("Arial", 10, "bold"), width=16, anchor="w").pack(side="left")
                tk.Label(row, text=f"{img.width}x{img.height} px", font=("Arial", 10), anchor="w").pack(side="left")
        except Exception:
            pass

    def go_prev():
        current[0] -= 1
        load(current[0])

    def go_next():
        current[0] += 1
        load(current[0])

    prev_btn.config(command=go_prev)
    next_btn.config(command=go_next)

    # File action buttons at bottom
    action_bar = tk.Frame(win)
    action_bar.pack(fill="x", pady=8)

    def do_rename():
        path = all_paths[current[0]]
        rename_win = tk.Toplevel(win)
        rename_win.title("Rename File")
        rename_win.geometry("400x120")
        tk.Label(rename_win, text="New name:", font=("Arial", 11)).pack(pady=8)
        entry = tk.Entry(rename_win, font=("Arial", 11), width=40)
        entry.insert(0, os.path.basename(path))
        entry.pack()
        def confirm():
            new_name = entry.get().strip()
            if new_name:
                ext = os.path.splitext(path)[1]
                if not new_name.lower().endswith(ext.lower()):
                    new_name += ext
                if new_name != os.path.basename(path):
                    backup_file(path)
                    new_path = os.path.join(os.path.dirname(path), new_name)
                    os.rename(path, new_path)
                    all_paths[current[0]] = new_path
                    load(current[0])
            rename_win.destroy()
        tk.Button(rename_win, text="Rename", font=("Arial", 11), command=confirm).pack(pady=8)

    def do_delete():
        path = all_paths[current[0]]
        confirm_win = tk.Toplevel(win)
        confirm_win.title("Delete File")
        confirm_win.geometry("400x120")
        tk.Label(confirm_win, text=f"Delete {os.path.basename(path)}?", font=("Arial", 11)).pack(pady=10)
        btn_row = tk.Frame(confirm_win)
        btn_row.pack()
        def confirm():
            backup_file(path)
            os.remove(path)
            all_paths.pop(current[0])
            confirm_win.destroy()
            if current[0] >= len(all_paths):
                current[0] = max(0, len(all_paths) - 1)
            if all_paths:
                load(current[0])
            else:
                win.destroy()
        tk.Button(btn_row, text="Yes, Delete", font=("Arial", 11), fg="red", command=confirm).pack(side="left", padx=10)
        tk.Button(btn_row, text="Cancel", font=("Arial", 11), command=confirm_win.destroy).pack(side="left", padx=10)

    def do_copy():
        from tkinter import filedialog
        path = all_paths[current[0]]
        dest_dir = filedialog.askdirectory(title="Copy to folder")
        if dest_dir:
            dest = os.path.join(dest_dir, os.path.basename(path))
            shutil.copy2(path, dest)
            tk.messagebox.showinfo("Copied", f"Copied to:\n{dest}")

    def do_move():
        from tkinter import filedialog
        path = all_paths[current[0]]
        dest_dir = filedialog.askdirectory(title="Move to folder")
        if dest_dir:
            backup_file(path)
            dest = os.path.join(dest_dir, os.path.basename(path))
            shutil.move(path, dest)
            all_paths[current[0]] = dest
            load(current[0])

    tk.Button(action_bar, text="Rename", font=("Arial", 11), width=10, command=do_rename).pack(side="left", padx=8)
    tk.Button(action_bar, text="Copy", font=("Arial", 11), width=10, command=do_copy).pack(side="left", padx=8)
    tk.Button(action_bar, text="Move", font=("Arial", 11), width=10, command=do_move).pack(side="left", padx=8)
    tk.Button(action_bar, text="Delete", font=("Arial", 11), width=10, fg="red", command=do_delete).pack(side="left", padx=8)

    load(current[0])

def on_select(event):
    global selected_filename
    node = tree.focus()
    text = tree.item(node, "text")
    if text and not text.startswith("/") and "." in text:
        selected_filename = text
        find_btn.config(state="normal", text=f'Find All Copies of "{text}"')
    else:
        selected_filename = None
        find_btn.config(state="disabled", text="Find All Copies")

def get_path(node):
    parts = []
    while node:
        parts.insert(0, tree.item(node, "text"))
        node = tree.parent(node)
    return os.path.join(start_path, *parts[1:])

def browse():
    tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    for item in tree.get_children():
        tree.delete(item)
    tree.heading("#0", text="File Tree", anchor="w")
    root_node = tree.insert("", "end", text=start_path, open=True)
    load_tree(start_path, root_node)

def apply_filter(extensions, window):
    global current_filter
    current_filter = extensions
    window.destroy()
    if extensions:
        search_all_by_type(extensions)
    else:
        browse()

def search_all_by_type(extensions):
    status_label.config(text=f"Searching entire computer for {', '.join(extensions)} files...")
    progress_bar.config(value=0)
    progress_bar.pack(padx=10, fill="x")
    tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    for item in tree.get_children():
        tree.delete(item)
    tree.heading("#0", text=f"All {', '.join(extensions)} files on this computer", anchor="w")

    def worker():
        # Auto-mount Windows drives if not already mounted
        for device, mount_point in zip(WINDOWS_DEVICES, WINDOWS_MOUNTS):
            if not os.path.ismount(mount_point):
                subprocess.run(
                    ["udisksctl", "mount", "-b", device, "--no-user-interaction"],
                    capture_output=True, text=True
                )

        LIMIT = 2000
        results = {"Linux": [], "Windows": []}
        skip_dirs = {"/proc", "/sys", "/dev", "/run", "/snap"}

        def update_progress(found, total_limit, phase):
            pct = min(int((found / total_limit) * 100), 99)
            root.after(0, lambda: status_label.config(text=f"Searching {phase}... {found} found ({pct}%)"))
            root.after(0, lambda: progress_bar.config(value=pct))

        # Search Linux — collect path + metadata in background
        for dirpath, dirnames, filenames in os.walk("/"):
            dirnames[:] = [
                d for d in dirnames
                if os.path.join(dirpath, d) not in skip_dirs
                and not any(os.path.join(dirpath, d).startswith(m) for m in WINDOWS_MOUNTS)
            ]
            for f in filenames:
                if any(f.lower().endswith(ext) for ext in extensions):
                    path = os.path.join(dirpath, f)
                    size, date, dims = get_metadata(path)
                    results["Linux"].append((path, size, date, dims))
                    if len(results["Linux"]) % 10 == 0:
                        update_progress(len(results["Linux"]), LIMIT // 2, "Linux")
            if len(results["Linux"]) >= LIMIT // 2:
                break

        # Search Windows mounts
        for mount in WINDOWS_MOUNTS:
            if os.path.ismount(mount):
                for dirpath, dirnames, filenames in os.walk(mount):
                    for f in filenames:
                        if any(f.lower().endswith(ext) for ext in extensions):
                            path = os.path.join(dirpath, f)
                            size, date, dims = get_metadata(path)
                            results["Windows"].append((path, size, date, dims))
                            if len(results["Windows"]) % 10 == 0:
                                update_progress(len(results["Windows"]), LIMIT // 2, "Windows")
                    if len(results["Windows"]) >= LIMIT // 2:
                        break

        def update_ui():
            progress_bar.config(value=100)
            progress_bar.pack_forget()

            linux_node = tree.insert("", "end", text=f"LINUX ({len(results['Linux'])} found)", open=True)
            for path, size, date, dims in results["Linux"]:
                tree.insert(linux_node, "end", text=os.path.basename(path), values=(path, size, date, dims))

            windows_node = tree.insert("", "end", text=f"WINDOWS ({len(results['Windows'])} found)", open=True)
            if results["Windows"]:
                for path, size, date, dims in results["Windows"]:
                    tree.insert(windows_node, "end", text=os.path.basename(path), values=(path, size, date, dims))
            else:
                tree.insert(windows_node, "end", text="No Windows drives mounted")

            total = len(results["Linux"]) + len(results["Windows"])
            status_label.config(text=f"{total} files found.")

        root.after(0, update_ui)

    threading.Thread(target=worker, daemon=True).start()

def filter_type():
    type_win = tk.Toplevel(root)
    type_win.title("File Type")
    type_win.geometry("250x200")

    tk.Label(type_win, text="Select file type:", font=("Arial", 12)).pack(pady=10)

    file_types = [
        ("All Files", []),
        ("Images", [".jpg", ".jpeg", ".png", ".gif"]),
        ("Videos", [".mp4", ".mov", ".avi"]),
        ("Documents", [".pdf", ".docx", ".txt"]),
    ]

    for name, exts in file_types:
        tk.Button(type_win, text=name, font=("Arial", 11), width=20,
                  command=lambda e=exts: apply_filter(e, type_win)).pack(pady=3)

def do_search(query):
    results = []
    skip_dirs = {"/proc", "/sys", "/dev", "/run"}
    for dirpath, dirnames, filenames in os.walk("/"):
        dirnames[:] = [d for d in dirnames if os.path.join(dirpath, d) not in skip_dirs]
        for filename in filenames:
            if query.lower() in filename.lower():
                results.append(os.path.join(dirpath, filename))
        if len(results) >= 500:
            break
    return results

def show_search_results(results, query):
    tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    for item in tree.get_children():
        tree.delete(item)
    tree.heading("#0", text=f"Search results for: {query}", anchor="w")
    if not results:
        tree.insert("", "end", text="No files found.")
    else:
        for path in results:
            tree.insert("", "end", text=os.path.basename(path))
    status_label.config(text=f"{len(results)} result(s) found.")

def run_search():
    query = search_entry.get().strip()
    if not query:
        return
    status_label.config(text="Searching...")
    search_btn.config(state="disabled")

    def worker():
        results = do_search(query)
        root.after(0, lambda: show_search_results(results, query))
        root.after(0, lambda: search_btn.config(state="normal"))

    threading.Thread(target=worker, daemon=True).start()

def mount_windows():
    status_label.config(text="Mounting Windows drives...")
    mounted = []
    errors = []
    for device, mount_point in zip(WINDOWS_DEVICES, WINDOWS_MOUNTS):
        result = subprocess.run(
            ["udisksctl", "mount", "-b", device, "--no-user-interaction"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            mounted.append(mount_point)
        else:
            errors.append(device)

    if mounted:
        status_label.config(text=f"Windows mounted at: {', '.join(mounted)}")
    if errors:
        status_label.config(text=f"Could not mount: {', '.join(errors)} — try running as admin")

def do_find_all_copies(filename):
    results = {"Linux": [], "Windows": []}
    skip_dirs = {"/proc", "/sys", "/dev", "/run", "/snap"}

    # Search Linux
    for dirpath, dirnames, filenames in os.walk("/"):
        dirnames[:] = [
            d for d in dirnames
            if os.path.join(dirpath, d) not in skip_dirs
            and not any(os.path.join(dirpath, d).startswith(m) for m in WINDOWS_MOUNTS)
        ]
        for f in filenames:
            if f.lower() == filename.lower():
                results["Linux"].append(os.path.join(dirpath, f))
        if len(results["Linux"]) >= 200:
            break

    # Search Windows mounts
    for mount in WINDOWS_MOUNTS:
        if os.path.ismount(mount):
            for dirpath, dirnames, filenames in os.walk(mount):
                for f in filenames:
                    if f.lower() == filename.lower():
                        results["Windows"].append(os.path.join(dirpath, f))
                if len(results["Windows"]) >= 200:
                    break

    return results

def show_copies(results, filename):
    tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    for item in tree.get_children():
        tree.delete(item)
    tree.heading("#0", text=f'All copies of "{filename}"', anchor="w")

    linux_node = tree.insert("", "end", text=f"LINUX ({len(results['Linux'])} found)", open=True)
    for path in results["Linux"]:
        size, date, dims = get_metadata(path)
        tree.insert(linux_node, "end", text=os.path.basename(path), values=(path, size, date, dims))

    windows_node = tree.insert("", "end", text=f"WINDOWS ({len(results['Windows'])} found)", open=True)
    if results["Windows"]:
        for path in results["Windows"]:
            size, date, dims = get_metadata(path)
            tree.insert(windows_node, "end", text=os.path.basename(path), values=(path, size, date, dims))
    else:
        tree.insert(windows_node, "end", text="No Windows drives mounted")

    total = len(results["Linux"]) + len(results["Windows"])
    status_label.config(text=f'{total} total copies of "{filename}" found.')

def run_find_all_copies():
    if not selected_filename:
        return
    status_label.config(text=f'Searching for all copies of "{selected_filename}"...')
    find_btn.config(state="disabled")

    def worker():
        results = do_find_all_copies(selected_filename)
        root.after(0, lambda: show_copies(results, selected_filename))
        root.after(0, lambda: find_btn.config(state="normal"))

    threading.Thread(target=worker, daemon=True).start()


start_path = os.path.expanduser("~")

root = tk.Tk()
root.title("FILE-COMMANDER")
root.geometry("1000x650")

# Search bar
search_frame = tk.Frame(root)
search_frame.pack(pady=(15, 5), padx=10, fill="x")

search_entry = tk.Entry(search_frame, font=("Arial", 13))
search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
search_entry.bind("<Return>", lambda e: run_search())

search_btn = tk.Button(search_frame, text="Search", font=("Arial", 13), width=10, command=run_search)
search_btn.pack(side="left")

status_label = tk.Label(root, text="", font=("Arial", 10), fg="gray")
status_label.pack()

progress_bar = ttk.Progressbar(root, mode="determinate", maximum=100, value=0)

# Buttons row 1
btn_frame = tk.Frame(root)
btn_frame.pack(pady=5)

browse_btn = tk.Button(btn_frame, text="Browse", font=("Arial", 13), width=12, command=browse)
browse_btn.pack(side="left", padx=10)

type_btn = tk.Button(btn_frame, text="File Type", font=("Arial", 13), width=12, command=filter_type)
type_btn.pack(side="left", padx=10)


# Buttons row 2
btn_frame2 = tk.Frame(root)
btn_frame2.pack(pady=5)

find_btn = tk.Button(btn_frame2, text="Find All Copies", font=("Arial", 13), width=40,
                     state="disabled", command=run_find_all_copies)
find_btn.pack(padx=10)

tree_frame = tk.Frame(root)

scrollbar = tk.Scrollbar(tree_frame)
scrollbar.pack(side="right", fill="y")

tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set, columns=("path", "size", "date", "dims"), displaycolumns=("size", "date", "dims"))
tree.pack(fill="both", expand=True)
scrollbar.config(command=tree.yview)

tree.heading("#0", text="File", anchor="w")
tree.heading("size", text="Size", anchor="w")
tree.heading("date", text="Date Modified", anchor="w")
tree.heading("dims", text="Dimensions", anchor="w")

tree.column("#0", width=350)
tree.column("size", width=100)
tree.column("date", width=160)
tree.column("dims", width=120)
tree.bind("<<TreeviewOpen>>", on_open)
tree.bind("<<TreeviewSelect>>", on_select)
tree.bind("<Double-1>", on_double_click)

root.mainloop()
