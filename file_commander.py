import tkinter as tk
from tkinter import ttk
import os
import threading

current_filter = []

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
    root_node = tree.insert("", "end", text=start_path, open=True)
    load_tree(start_path, root_node)

def apply_filter(extensions, window):
    global current_filter
    current_filter = extensions
    window.destroy()
    browse()

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
            tree.insert("", "end", text=path)
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

start_path = os.path.expanduser("~")

root = tk.Tk()
root.title("FILE-COMMANDER")
root.geometry("700x600")

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

# Browse / File Type buttons
btn_frame = tk.Frame(root)
btn_frame.pack(pady=5)

browse_btn = tk.Button(btn_frame, text="Browse", font=("Arial", 13), width=12, command=browse)
browse_btn.pack(side="left", padx=10)

type_btn = tk.Button(btn_frame, text="File Type", font=("Arial", 13), width=12, command=filter_type)
type_btn.pack(side="left", padx=10)

tree_frame = tk.Frame(root)

scrollbar = tk.Scrollbar(tree_frame)
scrollbar.pack(side="right", fill="y")

tree = ttk.Treeview(tree_frame, yscrollcommand=scrollbar.set)
tree.pack(fill="both", expand=True)
scrollbar.config(command=tree.yview)

tree.heading("#0", text="File Tree", anchor="w")
tree.bind("<<TreeviewOpen>>", on_open)

root.mainloop()
