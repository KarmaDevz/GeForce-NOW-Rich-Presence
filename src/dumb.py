import tkinter as tk
import ctypes

try:
    app_id = "NVIDIA.GeForceNOW"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
except Exception as e:
    print(f"⚠️ No se pudo establecer AppID: {e}")

root = tk.Tk()
root.title("PRAGMATA")
root.geometry("300x200")

label = tk.Label(root, text="PRAGMATA", font=("Arial", 12))
label.pack(expand=True)

root.overrideredirect(True)

root.mainloop()