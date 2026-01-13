import subprocess, sys, os, tkinter as tk
HERE = os.path.dirname(os.path.abspath(__file__))

def run(script):
    subprocess.Popen([sys.executable, os.path.join(HERE, script)])

root = tk.Tk()
root.title("VAT Refunder")
buttons = [
    ("Log Chancery Invoice",  "invoice_chy.py"),
    ("Log Personal Invoice",  "invoice_pers.py"),
    ("Log Residence Invoice", "invoice_res.py"),
    ("Log New Supplier", "new_supplier.py"),
    ("Log Voucher",           "vouchers.py"),
    ("Print Official VAT", "vat_oficial.py"),
    ("Print Personal VAT ", "vat_colleague.py"),
    ("Print Invoice-to-Voucher Report", "vat_vouchers.py"),
]
for text, script in buttons:
    tk.Button(root, text=text, width=28, command=lambda s=script: run(s)).pack(padx=16, pady=8)

tk.Label(root, text="MySQL must be running (Docker).").pack(pady=(6,12))
root.mainloop()