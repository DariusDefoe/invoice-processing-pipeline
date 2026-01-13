#!/usr/bin/env python3

import tkinter as tk
from tkinter import messagebox
from contextlib import contextmanager
from db import get_cnx  # central DB connector

# ==========================================================
# Context manager for automatic cleanup
# ==========================================================
@contextmanager
def db_cursor(commit=False):
    cnx = get_cnx()
    cur = cnx.cursor()
    try:
        yield cur
        if commit:
            cnx.commit()
    except Exception as e:
        cnx.rollback()
        raise e
    finally:
        cur.close()
        cnx.close()

# ==========================================================
# Fetch Budget Heads
# ==========================================================
def get_budget_heads():
    try:
        with db_cursor() as cur:
            cur.execute("SELECT Head_of_Accounts_ID, Name FROM Head_of_Accounts")
            rows = cur.fetchall()
            return {name: head_id for head_id, name in rows}
    except Exception as e:
        messagebox.showerror("Database Error", str(e))
        return {}

# ==========================================================
# Insert Voucher
# ==========================================================
def insert_voucher(data):
    try:
        with db_cursor(commit=True) as cur:
            sql = """
                INSERT INTO Vouchers
                (Voucher_Number, Head_of_Accounts_ID, Voucher_Beneficiary,
                 Voucher_Euro, Voucher_Quarter, Voucher_Year)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cur.execute(sql, data)
            voucher_id = cur.lastrowid
        messagebox.showinfo("Success", f"Voucher inserted with ID: {voucher_id}")
    except Exception as e:
        messagebox.showerror("Insert Error", str(e))


def submit():
    # ▶ basic normalization/validation
    voucher_number = entry_voucher_number.get().strip().zfill(10)
    beneficiary = entry_beneficiary.get().strip()
    euro_txt = entry_euro.get().strip().replace(",", ".")
    quarter_txt = entry_quarter.get().strip()
    year_txt = entry_year.get().strip()
    bh_name = budget_head_var.get().strip()
    head_id = budget_heads.get(bh_name)

# ==========================================================
# Data validation
# ==========================================================
    try:
        euro = float(euro_txt)
        quarter = int(quarter_txt)
        year = int(year_txt)
        assert 1 <= quarter <= 4
        assert 2000 <= year <= 2100
        if not (voucher_number and beneficiary and head_id):
            raise ValueError("Missing fields")
    except Exception:
        messagebox.showwarning("Input Error", "Check: number, beneficiary, euro, quarter (1–4), year, budget head.")
        return

    try:
        insert_voucher((voucher_number, head_id, beneficiary, euro, quarter, year))
        # ▶ optional: clear fields on success
        entry_beneficiary.delete(0, tk.END)
        entry_euro.delete(0, tk.END)
        entry_quarter.delete(0, tk.END)
        entry_year.delete(0, tk.END)
    except Exception as e:
        messagebox.showerror("Data Error", str(e))

# ==========================================================
# Main app GUI
# ==========================================================
root = tk.Tk()
root.title("Insert Voucher")
root.geometry("")
root.configure(bg="lightblue")

label_options = {"bg": "lightblue", "font": ("Helvetica", 12)}

tk.Label(root, text="Voucher Number", **label_options).grid(row=0, column=0, padx=10, pady=10, sticky="w")
entry_voucher_number = tk.Entry(root, font=("Helvetica", 12))
entry_voucher_number.grid(row=0, column=1, padx=10, pady=10)

tk.Label(root, text="Voucher Beneficiary", **label_options).grid(row=1, column=0, padx=10, pady=10, sticky="w")
entry_beneficiary = tk.Entry(root, font=("Helvetica", 12))
entry_beneficiary.grid(row=1, column=1, padx=10, pady=10)

tk.Label(root, text="Voucher Euro", **label_options).grid(row=2, column=0, padx=10, pady=10, sticky="w")
entry_euro = tk.Entry(root, font=("Helvetica", 12))
entry_euro.grid(row=2, column=1, padx=10, pady=10)

tk.Label(root, text="Voucher Quarter", **label_options).grid(row=3, column=0, padx=10, pady=10, sticky="w")
entry_quarter = tk.Entry(root, font=("Helvetica", 12))
entry_quarter.grid(row=3, column=1, padx=10, pady=10)

tk.Label(root, text="Voucher Year", **label_options).grid(row=4, column=0, padx=10, pady=10, sticky="w")
entry_year = tk.Entry(root, font=("Helvetica", 12))
entry_year.grid(row=4, column=1, padx=10, pady=10)

tk.Label(root, text="Budget Head", **label_options).grid(row=5, column=0, padx=10, pady=10, sticky="w")
budget_heads = get_budget_heads()
budget_head_var = tk.StringVar(root)
if budget_heads:
    budget_head_var.set(list(budget_heads.keys())[0])
option_menu = tk.OptionMenu(root, budget_head_var, *budget_heads.keys())
option_menu.config(font=("Helvetica", 12))
option_menu.grid(row=5, column=1, padx=10, pady=10)

tk.Button(root, text="Submit", command=submit, font=("Helvetica", 12)).grid(row=6, column=0, columnspan=2, pady=20)

root.mainloop()
