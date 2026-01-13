#!/usr/bin/env python3

import os
from contextlib import contextmanager
from db import get_cnx  # central DB connector
import tkinter as tk
from tkinter import ttk, messagebox
from mysql.connector import Error
from datetime import datetime
import csv

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
# Autocomplete Combobox Class
# ==========================================================

class AutocompleteCombobox(ttk.Combobox):
    def set_completion_list(self, completion_list):
        self._completion_list = sorted(completion_list, key=str.lower)
        self['values'] = self._completion_list
        self.bind('<KeyRelease>', self._handle_keyrelease)
        self.bind('<<ComboboxSelected>>', self._handle_selected)
    def _handle_keyrelease(self, event):
        if event.keysym in ("BackSpace", "Left", "Right", "Up", "Down", "Return", "Escape"):
            return
        value = self.get().lower()
        matches = [item for item in self._completion_list if item.lower().startswith(value)]
        self['values'] = matches if matches else self._completion_list
        if matches:
            self.event_generate('<Down>')
    def _handle_selected(self, event):
        pass

# ==========================================================
# VAT Calculation Function
# ==========================================================

def calculate_vat_from_total(total_amount):
    return total_amount * 21 / 121

# ==========================================================
# Database Fetch Functions
# ==========================================================

def fetch_supplier_data():
    try:
        with db_cursor(commit=False) as cur: 
            cur.execute("SELECT Supplier_ID, Supplier_Name FROM NIF_Codes")
            suppliers = cur.fetchall()
            return suppliers
    except Error as e:
        messagebox.showerror("Database Error", f"Error fetching suppliers: {e}")
        return []

def fetch_budget_heads():
    try:
        with db_cursor(commit=False) as cur:
            cur.execute("SELECT Head_of_Accounts_ID, Head_of_Accounts_Name FROM Head_of_Accounts")
            rows = cur.fetchall()
            return {name: head_id for head_id, name in rows}
    except Error as e:
        messagebox.showerror("Database Error", f"Error fetching budget heads: {e}")
        return {}

# ==========================================================
# Event Handlers
# ==========================================================
def submit_chancery_transaction():
    supplier_name = supplier_var.get()
    invoice_number = invoice_number_entry.get().strip()
    invoice_date = invoice_date_entry.get().strip()
    invoice_amount = invoice_amount_entry.get().strip()
    invoice_vat = invoice_vat_entry.get().strip()
    vat_refundable = vat_refundable_var.get()
    status = status_var.get()

    if not all([supplier_name, invoice_number, invoice_date, invoice_amount, invoice_vat, status]):
        status_label.config(text="Please fill in all required invoice fields.", fg="red")
        return

    try:
        invoice_amount = float(invoice_amount)
        invoice_vat = float(invoice_vat)
    except ValueError:
        messagebox.showwarning("Input Error", "Invoice Amount and VAT must be numbers.")
        status_label.config(text="Invalid numeric input.", fg="red")
        return

    try:
        datetime.strptime(invoice_date, '%Y-%m-%d')
    except ValueError:
        messagebox.showwarning("Input Error", "Invalid date format for Invoice Date. Use YYYY-MM-DD.")
        status_label.config(text="Invalid date format.", fg="red")
        return

    supplier_id = supplier_id_map.get(supplier_name)
    if not supplier_id:
        messagebox.showwarning("Input Error", f"Supplier '{supplier_name}' not found.")
        status_label.config(text="Invalid supplier selected.", fg="red")
        return

    voucher_id = None
    voucher_number_raw = entry_voucher_number.get().strip()
    if voucher_number_raw:
        voucher_number = voucher_number_raw.zfill(10)
        beneficiary = entry_voucher_beneficiary.get().strip()
        voucher_euro = entry_voucher_euro.get().strip()
        voucher_quarter = entry_voucher_quarter.get().strip()
        voucher_year = entry_voucher_year.get().strip()
        budget_head_name = budget_head_var.get()

        if not all([voucher_number, beneficiary, voucher_euro, voucher_quarter, voucher_year, budget_head_name]):
            messagebox.showwarning("Input Error", "Please fill all voucher fields.")
            return
        try:
            voucher_euro = float(voucher_euro)
            voucher_quarter = int(voucher_quarter)
            voucher_year = int(voucher_year)
        except ValueError:
            messagebox.showwarning("Input Error", "Voucher Euro must be a number; Quarter and Year must be integers.")
            return

        head_id = budget_heads.get(budget_head_name)
        if not head_id:
            messagebox.showwarning("Input Error", f"Budget head '{budget_head_name}' not found.")
            return

    try:
        with db_cursor(commit=True) as cur:
            # Duplicate check
            cur.execute("SELECT 1 FROM Invoices_Chancery WHERE Number = %s", (invoice_number,))
            if cur.fetchone():
                messagebox.showerror("Duplicate Invoice", "An invoice with this number already exists.")
                status_label.config(text="Duplicate invoice number.", fg="red")
                return
            if voucher_number_raw:
                voucher_query = """
                    INSERT INTO Vouchers (Voucher_Number, Head_of_Accounts_ID, Voucher_Beneficiary,
                                          Voucher_Euro, Voucher_Quarter, Voucher_Year)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """
                cur.execute(voucher_query, (voucher_number, head_id, beneficiary,
                                            voucher_euro, voucher_quarter, voucher_year))
                voucher_id = cur.lastrowid

            invoice_query = """
                INSERT INTO Invoices_Chancery
                    (Supplier_ID, Number, Date, Total, Vat, Refundable, Status, Voucher_ID)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(invoice_query, (supplier_id, invoice_number, invoice_date,
                                        invoice_amount, invoice_vat, vat_refundable, status, voucher_id))
            # success UI (outside with:)
        if voucher_id:
            messagebox.showinfo("Success",
                                f"Invoice submitted successfully.")
        else:
            messagebox.showinfo("Success",
                                f"Invoice submitted successfully.")
        status_label.config(text="Invoice submitted successfully.", fg="green")
        clear_fields()

    except Exception as e:
        messagebox.showerror("Database Error", f"Error submitting invoice: {e}")
        status_label.config(text="Error submitting invoice.", fg="red")

def clear_fields():
    supplier_var.set('')
    invoice_number_entry.delete(0, tk.END)
    invoice_date_entry.delete(0, tk.END)
    invoice_amount_entry.delete(0, tk.END)
    invoice_vat_entry.delete(0, tk.END)
    vat_refundable_var.set(0)
    status_var.set('')
    vat_21_var.set(0)
    invoice_vat_entry.config(state='normal')
    entry_voucher_number.delete(0, tk.END)
    entry_voucher_beneficiary.delete(0, tk.END)
    entry_voucher_euro.delete(0, tk.END)
    entry_voucher_quarter.delete(0, tk.END)
    entry_voucher_year.delete(0, tk.END)
    budget_head_var.set('')

def on_vat_checkbox_toggle():
    if vat_21_var.get():
        try:
            total_amount = float(invoice_amount_entry.get())
            vat = calculate_vat_from_total(total_amount)
            invoice_vat_entry.delete(0, tk.END)
            invoice_vat_entry.insert(0, f"{vat:.2f}")
            invoice_vat_entry.config(state='readonly')
        except ValueError:
            messagebox.showwarning("Input Error", "Enter a valid Invoice Amount before calculating VAT.")
            vat_21_var.set(0)
    else:
        invoice_vat_entry.config(state='normal')

def on_invoice_amount_change(*args):
    if vat_21_var.get():
        try:
            total_amount = float(invoice_amount_var.get())
            vat = calculate_vat_from_total(total_amount)
            invoice_vat_var.set(f"{vat:.2f}")
        except ValueError:
            invoice_vat_var.set("")

# ==========================================================
# Fetch Data
# ==========================================================
suppliers = fetch_supplier_data()
supplier_id_map = {supplier[1]: supplier[0] for supplier in suppliers}
budget_heads = fetch_budget_heads()

# ==========================================================
# Tkinter GUI Setup
# ==========================================================
root = tk.Tk()
root.title("Chancery Invoice Entry Form")
root.geometry("800x700")

label_font = ("Helvetica", 12)
button_font = ("Helvetica", 12)
entry_width = 40

# Invoice Section
tk.Label(root, text="Supplier:", font=label_font).grid(row=0, column=0, padx=10, pady=10, sticky="e")
supplier_var = tk.StringVar()
supplier_dropdown = AutocompleteCombobox(root, textvariable=supplier_var, font=label_font, width=entry_width-10)
supplier_dropdown.set_completion_list([supplier[1] for supplier in suppliers])
supplier_dropdown.grid(row=0, column=1, padx=10, pady=10, sticky="w")

tk.Label(root, text="Invoice Number:", font=label_font).grid(row=1, column=0, padx=10, pady=10, sticky="e")
invoice_number_entry = tk.Entry(root, font=label_font, width=entry_width)
invoice_number_entry.grid(row=1, column=1, padx=10, pady=10, sticky="w")

tk.Label(root, text="Invoice Date (YYYY-MM-DD):", font=label_font).grid(row=2, column=0, padx=10, pady=10, sticky="e")
invoice_date_entry = tk.Entry(root, font=label_font, width=entry_width)
invoice_date_entry.grid(row=2, column=1, padx=10, pady=10, sticky="w")

tk.Label(root, text="Invoice Amount (€):", font=label_font).grid(row=3, column=0, padx=10, pady=10, sticky="e")
invoice_amount_var = tk.StringVar()
invoice_amount_entry = tk.Entry(root, textvariable=invoice_amount_var, font=label_font, width=entry_width)
invoice_amount_entry.grid(row=3, column=1, padx=10, pady=10, sticky="w")
invoice_amount_var.trace_add('write', on_invoice_amount_change)

vat_21_var = tk.IntVar()
vat_checkbox = tk.Checkbutton(root, text="Is VAT 21%?", variable=vat_21_var, font=label_font, command=on_vat_checkbox_toggle)
vat_checkbox.grid(row=4, column=0, padx=10, pady=10, sticky="e")

tk.Label(root, text="Invoice VAT (€):", font=label_font).grid(row=4, column=0, padx=10, pady=10, sticky="e")
invoice_vat_var = tk.StringVar()
invoice_vat_entry = tk.Entry(root, textvariable=invoice_vat_var, font=label_font, width=entry_width)
invoice_vat_entry.grid(row=4, column=1, padx=10, pady=10, sticky="e")

tk.Label(root, text="Refundable:", font=label_font).grid(row=5, column=0, padx=10, pady=10, sticky="e")
vat_refundable_var = tk.IntVar()
tk.Checkbutton(root, variable=vat_refundable_var, font=label_font).grid(row=5, column=1, padx=10, pady=10, sticky="w")

tk.Label(root, text="Status:", font=label_font).grid(row=6, column=0, padx=10, pady=10, sticky="e")
status_var = tk.StringVar()
status_dropdown = ttk.Combobox(root, textvariable=status_var, font=label_font, width=entry_width-10, state="readonly")
status_dropdown['values'] = ["Pending", "Processed", "Archived"]
status_dropdown.grid(row=6, column=1, padx=10, pady=10, sticky="w")

# Voucher Section Separator
separator = ttk.Separator(root, orient='horizontal')
separator.grid(row=7, column=0, columnspan=3, sticky="ew", padx=10, pady=20)

tk.Label(root, text="Voucher Entry (Optional):", font=("Helvetica", 14, "bold")).grid(row=8, column=0, columnspan=3, padx=10, pady=10)

tk.Label(root, text="Voucher Number:", font=label_font).grid(row=9, column=0, padx=10, pady=5, sticky="e")
entry_voucher_number = tk.Entry(root, font=label_font, width=entry_width)
entry_voucher_number.grid(row=9, column=1, padx=10, pady=5, sticky="w")

tk.Label(root, text="Voucher Beneficiary:", font=label_font).grid(row=10, column=0, padx=10, pady=5, sticky="e")
entry_voucher_beneficiary = tk.Entry(root, font=label_font, width=entry_width)
entry_voucher_beneficiary.grid(row=10, column=1, padx=10, pady=5, sticky="w")

tk.Label(root, text="Voucher Euro (€):", font=label_font).grid(row=11, column=0, padx=10, pady=5, sticky="e")
entry_voucher_euro = tk.Entry(root, font=label_font, width=entry_width)
entry_voucher_euro.grid(row=11, column=1, padx=10, pady=5, sticky="w")

tk.Label(root, text="Voucher Quarter:", font=label_font).grid(row=12, column=0, padx=10, pady=5, sticky="e")
entry_voucher_quarter = tk.Entry(root, font=label_font, width=entry_width)
entry_voucher_quarter.grid(row=12, column=1, padx=10, pady=5, sticky="w")

tk.Label(root, text="Voucher Year:", font=label_font).grid(row=13, column=0, padx=10, pady=5, sticky="e")
entry_voucher_year = tk.Entry(root, font=label_font, width=entry_width)
entry_voucher_year.grid(row=13, column=1, padx=10, pady=5, sticky="w")

tk.Label(root, text="Budget Head:", font=label_font).grid(row=14, column=0, padx=10, pady=5, sticky="e")
budget_head_var = tk.StringVar()
if budget_heads:
    budget_head_var.set(list(budget_heads.keys())[0])
budget_head_menu = tk.OptionMenu(root, budget_head_var, *budget_heads.keys())
budget_head_menu.config(font=label_font)
budget_head_menu.grid(row=14, column=1, padx=10, pady=5, sticky="w")

submit_button = tk.Button(root, text="Submit", command=submit_chancery_transaction, font=button_font, bg="#4CAF50", fg="white", width=15)
submit_button.grid(row=15, column=1, padx=10, pady=20, sticky="w")

status_label = tk.Label(root, text="", font=label_font)
status_label.grid(row=19, column=0, columnspan=3, padx=10, pady=10, sticky="w")

root.mainloop()
