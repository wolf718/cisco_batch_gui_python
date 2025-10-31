import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from netmiko import ConnectHandler
import csv
import os
from datetime import datetime
import threading
import queue

# ===== 多语言文本 =====
LANG_TEXT = {
   "CN": {
       "title": "Cisco 批量配置工具",
       "select_csv": "选择 CSV 文件",
       "export_template": "导出 CSV 模板",
       "select_log": "选择日志保存位置",
       "use_enable": "使用 enable 密码",
       "change_hostname": "修改 hostname（从CSV读取）",
       "auto_save_config": "自动保存配置（write memory）",
       "multi_thread": "多线程批量执行",
       "thread_count": "最大并发线程数：",
       "clear_log": "清空日志",
       "cmd_label": "输入要执行的命令（每行一条，**不用输入 configure terminal/conf t，工具会自动进入配置模式**）:",
       "run_button": "运行批量配置",
       "lang_switch": "Switch to English",
       "success": "批量配置执行完毕\n日志已保存到:\n"
   },
   "EN": {
       "title": "Cisco Batch Configuration Tool",
       "select_csv": "Select CSV File",
       "export_template": "Export CSV Template",
       "select_log": "Select Log Save Location",
       "use_enable": "Use enable password",
       "change_hostname": "Change hostname (from CSV)",
       "auto_save_config": "Auto save config (write memory)",
       "multi_thread": "Run in Multi-thread mode",
       "thread_count": "Max concurrent threads:",
       "clear_log": "Clear log",
       "cmd_label": "Enter commands (one per line, **No need to enter configure terminal/conf t; tool will auto enter config mode**):",
       "run_button": "Run Batch Configuration",
       "lang_switch": "切换到中文",
       "success": "Batch configuration completed\nLog saved to:\n"
   }
}

current_lang = "CN"
gui_queue = queue.Queue()

# ===== GUI语言切换 =====
def switch_language():
   global current_lang
   current_lang = "EN" if current_lang == "CN" else "CN"
   update_labels()

def update_labels():
   root.title(LANG_TEXT[current_lang]["title"])
   btn_select_csv.config(text=LANG_TEXT[current_lang]["select_csv"])
   btn_export_template.config(text=LANG_TEXT[current_lang]["export_template"])
   btn_select_log.config(text=LANG_TEXT[current_lang]["select_log"])
   chk_use_enable.config(text=LANG_TEXT[current_lang]["use_enable"])
   chk_change_hostname.config(text=LANG_TEXT[current_lang]["change_hostname"])
   chk_auto_save_config.config(text=LANG_TEXT[current_lang]["auto_save_config"])
   chk_multi_thread.config(text=LANG_TEXT[current_lang]["multi_thread"])
   lbl_thread_count.config(text=LANG_TEXT[current_lang]["thread_count"])
   btn_clear_log.config(text=LANG_TEXT[current_lang]["clear_log"])
   lbl_cmd.config(text=LANG_TEXT[current_lang]["cmd_label"])
   btn_run.config(text=LANG_TEXT[current_lang]["run_button"])
   btn_lang_switch.config(text=LANG_TEXT[current_lang]["lang_switch"])

# ===== 选择日志文件 =====
def select_logfile():
   file_path = filedialog.asksaveasfilename(
       defaultextension=".log",
       filetypes=[("日志文件", "*.log")] if current_lang == "CN" else [("Log files", "*.log")],
       title=LANG_TEXT[current_lang]["select_log"],
       initialfile=f"batch_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
   )
   log_path.set(file_path)

# ===== 清空日志 =====
def clear_log():
   log_output.delete("1.0", tk.END)

# ===== 导出CSV模板（修复功能） =====
def export_template():
   file_path = filedialog.asksaveasfilename(
       defaultextension=".csv",
       filetypes=[("CSV 文件", "*.csv")] if current_lang == "CN" else [("CSV files", "*.csv")],
       title=LANG_TEXT[current_lang]["export_template"],
       initialfile="devices_template.csv"
   )
   if file_path:
       try:
           with open(file_path, 'w', newline='', encoding='utf-8') as f:
               writer = csv.writer(f)
               writer.writerow(["IP", "Username", "Password", "Secret", "NewHostname"])
               writer.writerow(["192.168.1.10", "admin", "pass123", "enablepass", "switch-a"])
               writer.writerow(["192.168.1.11", "admin", "pass456", "", "switch-b"])
           messagebox.showinfo(
               "成功" if current_lang == "CN" else "Success",
               f"模板已保存到:\n{file_path}" if current_lang == "CN" else f"Template saved to:\n{file_path}"
           )
       except Exception as e:
           messagebox.showerror("错误" if current_lang == "CN" else "Error", str(e))

# ===== 单台设备执行逻辑（在线程中运行） =====
def execute_device(device, custom_commands, change_hostname_flag, new_hostname, use_enable_flag, auto_save_flag, logfile, sem):
   with sem:
       with open(logfile, "a", encoding="utf-8") as lf:
           ip = device["connection"]["ip"]
           gui_queue.put(("log", f"=== {('正在配置' if current_lang=='CN' else 'Configuring')} {ip} ===\n"))
           lf.write(f"=== Configuring {ip} ===\n")
           try:
               net_connect = ConnectHandler(**device["connection"])
               if use_enable_flag and device["connection"]["secret"]:
                   net_connect.enable()

               gui_queue.put(("log", f"[info] Prompt: {net_connect.find_prompt()}\n"))
               lf.write(f"[info] Prompt: {net_connect.find_prompt()}\n")

               if custom_commands:
                   output1 = net_connect.send_config_set(custom_commands)
                   gui_queue.put(("log", output1 + "\n"))
                   lf.write(output1 + "\n")

               if change_hostname_flag and new_hostname:
                   output2 = net_connect.send_config_set([f"hostname {new_hostname}"])
                   gui_queue.put(("log", output2 + "\n"))
                   lf.write(output2 + "\n")
                   net_connect.set_base_prompt()
                   gui_queue.put(("log", f"[info] New Prompt: {net_connect.find_prompt()}\n"))
                   lf.write(f"[info] New Prompt: {net_connect.find_prompt()}\n")

               if auto_save_flag:
                   save_output = net_connect.save_config()
                   gui_queue.put(("log", save_output + "\n"))
                   lf.write(save_output + "\n")

               net_connect.disconnect()
               gui_queue.put(("log", f"=== {('配置完成' if current_lang=='CN' else 'Completed')} {ip} ===\n\n"))
               lf.write(f"=== Completed {ip} ===\n\n")
           except Exception as e:
               err_msg = f"!!! {('配置失败' if current_lang=='CN' else 'Failed')} {ip}: {e}\n\n"
               gui_queue.put(("log", err_msg))
               lf.write(err_msg)
       gui_queue.put(("progress", 1))

# ===== 主批量执行函数 =====
def run_batch():
   csv_file = csv_path.get()
   commands_text = commands_input.get("1.0", tk.END).strip()
   use_enable_flag = use_enable.get()
   change_hostname_flag = change_hostname.get()
   auto_save_flag = auto_save_config.get()
   multi_thread_flag = multi_thread.get()
   max_threads = int(thread_count.get()) if thread_count.get().isdigit() else 5

   if not csv_file:
       messagebox.showerror("错误" if current_lang=="CN" else "Error",
                            "请先选择 CSV 文件" if current_lang=="CN" else "Please select CSV file")
       return
   if not change_hostname_flag and not commands_text:
       messagebox.showerror("错误" if current_lang=="CN" else "Error",
                            "未勾选修改 hostname 时，必须输入命令" if current_lang=="CN" else "Commands required if not changing hostname")
       return

   logfile = log_path.get()
   if not logfile:
       logfile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              f"batch_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

   try:
       devices = []
       with open(csv_file, 'r') as f:
           reader = csv.DictReader(f)
           csv_headers = reader.fieldnames
           if change_hostname_flag and "NewHostname" not in csv_headers:
               messagebox.showerror("错误" if current_lang=="CN" else "Error",
                                    "CSV 文件缺少 'NewHostname' 列" if current_lang=="CN" else "CSV missing 'NewHostname' column")
               return
           for row in reader:
               devices.append({
                   "connection": {
                       'device_type': 'cisco_ios',
                       'ip': row['IP'],
                       'username': row['Username'],
                       'password': row['Password'],
                       'secret': row.get('Secret', '')
                   },
                   "new_hostname": row.get('NewHostname', '') if change_hostname_flag else ''
               })

       custom_commands = []
       if commands_text:
           custom_commands = [line.strip() for line in commands_text.split("\n") if line.strip()]
       elif change_hostname_flag:
           custom_commands = []

       log_output.delete("1.0", tk.END)
       progress_bar["maximum"] = len(devices)
       progress_bar["value"] = 0

       if multi_thread_flag:
           sem = threading.Semaphore(max_threads)
           for device in devices:
               threading.Thread(target=execute_device,
                                args=(device, custom_commands,
                                      change_hostname_flag, device["new_hostname"],
                                      use_enable_flag, auto_save_flag, logfile, sem)).start()
       else:
           for device in devices:
               execute_device(device, custom_commands, change_hostname_flag, device["new_hostname"],
                              use_enable_flag, auto_save_flag, logfile, threading.Semaphore(1))

   except Exception as e:
       messagebox.showerror("错误" if current_lang=="CN" else "Error", str(e))

# ===== 队列刷新 =====
def process_queue():
   while not gui_queue.empty():
       msg_type, msg_content = gui_queue.get()
       if msg_type == "log":
           log_output.insert(tk.END, msg_content)
           log_output.see(tk.END)
       elif msg_type == "progress":
           progress_bar.step(msg_content)
   root.after(100, process_queue)

# ===== GUI构造 =====
root = tk.Tk()
root.title(LANG_TEXT[current_lang]["title"])
root.geometry("880x860")

csv_path, log_path = tk.StringVar(), tk.StringVar()
use_enable = tk.BooleanVar()
change_hostname = tk.BooleanVar()
auto_save_config = tk.BooleanVar()
multi_thread = tk.BooleanVar()
thread_count = tk.StringVar(value="5")

frame_csv = tk.Frame(root)
frame_csv.pack(pady=5, fill=tk.X)
btn_select_csv = tk.Button(frame_csv, text=LANG_TEXT[current_lang]["select_csv"],
                          command=lambda: csv_path.set(filedialog.askopenfilename(filetypes=[("CSV 文件", "*.csv")])))
btn_select_csv.pack(side=tk.LEFT, padx=5)
tk.Entry(frame_csv, textvariable=csv_path, width=60).pack(side=tk.LEFT, padx=5)
btn_export_template = tk.Button(frame_csv, text=LANG_TEXT[current_lang]["export_template"], command=export_template)
btn_export_template.pack(side=tk.LEFT, padx=5)

frame_log = tk.Frame(root)
frame_log.pack(pady=5, fill=tk.X)
btn_select_log = tk.Button(frame_log, text=LANG_TEXT[current_lang]["select_log"], command=select_logfile)
btn_select_log.pack(side=tk.LEFT, padx=5)
tk.Entry(frame_log, textvariable=log_path, width=60).pack(side=tk.LEFT, padx=5)

chk_use_enable = tk.Checkbutton(root, text=LANG_TEXT[current_lang]["use_enable"], variable=use_enable)
chk_use_enable.pack(pady=5)
chk_change_hostname = tk.Checkbutton(root, text=LANG_TEXT[current_lang]["change_hostname"], variable=change_hostname)
chk_change_hostname.pack(pady=5)
chk_auto_save_config = tk.Checkbutton(root, text=LANG_TEXT[current_lang]["auto_save_config"], variable=auto_save_config)
chk_auto_save_config.pack(pady=5)
chk_multi_thread = tk.Checkbutton(root, text=LANG_TEXT[current_lang]["multi_thread"], variable=multi_thread)
chk_multi_thread.pack(pady=5)

frame_threads = tk.Frame(root)
frame_threads.pack(pady=5, fill=tk.X)
lbl_thread_count = tk.Label(frame_threads, text=LANG_TEXT[current_lang]["thread_count"])
lbl_thread_count.pack(side=tk.LEFT, padx=5)
tk.Entry(frame_threads, textvariable=thread_count, width=5).pack(side=tk.LEFT)

lbl_cmd = tk.Label(root, text=LANG_TEXT[current_lang]["cmd_label"], fg="blue")
lbl_cmd.pack(pady=5)
commands_input = tk.Text(root, height=8, wrap=tk.WORD)
commands_input.pack(expand=False, fill=tk.BOTH, padx=5)

btn_run = tk.Button(root, text=LANG_TEXT[current_lang]["run_button"], command=run_batch)
btn_run.pack(pady=10)
progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
progress_bar.pack(pady=5)

btn_lang_switch = tk.Button(root, text=LANG_TEXT[current_lang]["lang_switch"], command=switch_language)
btn_lang_switch.pack(pady=5)
btn_clear_log = tk.Button(root, text=LANG_TEXT[current_lang]["clear_log"], command=clear_log)
btn_clear_log.pack(pady=5)

log_output = tk.Text(root, wrap=tk.WORD)
log_output.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

root.after(100, process_queue)
root.mainloop()
