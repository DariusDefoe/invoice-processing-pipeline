#!/usr/bin/env python3
import csv
from decimal import Decimal, ROUND_HALF_UP, getcontext
import re
import math
from urllib.parse import urlparse
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date
import os
from dotenv import load_dotenv

load_dotenv()

# ===================== GLOBAL CONFIG =====================
getcontext().rounding = ROUND_HALF_UP
getcontext().prec = 28

DEFAULT_OFFICE = "Chancery"
DEFAULT_HEAD = "OE, CHANCERY"
DEFAULT_STATUS = "Processed"

# ===================== Autocomplete Combobox =====================
class AutocompleteCombobox(ttk.Combobox):
    def set_completion_list(self, completion_list):
        self._completion_list = sorted(completion_list, key=str.lower)
        self['values'] = self._completion_list
        self.bind('<KeyRelease>', self._handle_keyrelease)
    
    def _handle_keyrelease(self, event):
        if event.keysym in ("BackSpace", "Left", "Right", "Up", "Down", "Return", "Escape"):
            return
        value = self.get().lower()
        matches = [item for item in self._completion_list if item.lower().startswith(value)]
        self['values'] = matches if matches else self._completion_list
        if matches:
            self.event_generate('<Down>')

# ===================== DB Config =====================
mysql_conn = os.environ.get("MYSQL_CONNECTION")
if mysql_conn:
    url = urlparse(mysql_conn)
    db_config = {
        "host": url.hostname,
        "user": url.username,
        "password": url.password,
        "database": url.path.lstrip('/'),
        "port": url.port if url.port else 3306
    }
else:
    db_config = {
        "host": os.environ.get("DB_HOST"),
        "user": os.environ.get("DB_USER"),
        "password": os.environ.get("DB_PASSWORD"),
        "database": os.environ.get("DB_NAME")
    }

# ===================== DB Fetch =====================
def fetch_suppliers():
    try:
        conn = mysql.connector.connect(**db_config)
        cur = conn.cursor()
        cur.execute("SELECT Supplier_ID, Supplier_Name FROM NIF_Codes")
        return cur.fetchall()
    except Error:
        return []
    finally:
        if 'conn' in locals() and conn.is_connected():
            cur.close(); conn.close()

def fetch_budget_heads():
    try:
        conn = mysql.connector.connect(**db_config)
        cur = conn.cursor()
        cur.execute("SELECT Head_of_Accounts_ID, Head_of_Accounts_Name FROM Head_of_Accounts")
        rows = cur.fetchall()
        return {name: head_id for head_id, name in rows}
    except Error:
        return {}
    finally:
        if 'conn' in locals() and conn.is_connected():
            cur.close(); conn.close()

def fetch_beneficiaries():
    try:
        conn = mysql.connector.connect(**db_config)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT Voucher_Beneficiary FROM Vouchers WHERE Voucher_Beneficiary IS NOT NULL AND Voucher_Beneficiary != ''")
        rows = cur.fetchall()
        return [row[0] for row in rows]
    except Error:
        return []
    finally:
        if 'conn' in locals() and conn.is_connected():
            cur.close(); conn.close()

# ===================== Utils =====================
def calculate_vat_generic(total_amount, percentage):
    if not isinstance(total_amount, Decimal):
        try:
            total_amount = Decimal(str(total_amount))
        except:
            return Decimal('0.00')
    if percentage == 0:
        return Decimal('0.00')
    rate = Decimal(str(percentage))
    divisor = Decimal('100') + rate
    vat = total_amount * rate / divisor
    return vat.quantize(Decimal('0.01'))

def update_voucher_euro_default():
    total_vat = Decimal('0.00')
    for inv in invoices_list:
        val = inv['invoice_vat']
        if not isinstance(val, Decimal):
            val = Decimal(str(val))
        total_vat += val
    entry_voucher_euro.delete(0, tk.END)
    entry_voucher_euro.insert(0, f"{total_vat:.2f}")

def pad_voucher_number(s):
    return s.zfill(10)

def on_voucher_number_change(event):
    val = entry_voucher_number.get().strip()
    if len(val) >= 5:
        try:
            year_part = val[-3:-1]
            month_part = val[-5:-3]
            year_full = int("20" + year_part)
            month_int = int(month_part)
            if 1 <= month_int <= 12:
                quarter = (month_int - 1) // 3 + 1
                entry_voucher_year.delete(0, tk.END)
                entry_voucher_year.insert(0, str(year_full))
                entry_voucher_quarter.delete(0, tk.END)
                entry_voucher_quarter.insert(0, str(quarter))
        except ValueError:
            pass

def auto_suggest_beneficiary(*args):
    supp_name = supplier_var.get().strip()
    if not supp_name:
        return
    pattern = re.compile(re.escape(supp_name), re.IGNORECASE)
    best_match = ""
    for ben in beneficiaries_list:
        if pattern.search(ben):
            best_match = ben
            if supp_name.lower() == ben.lower():
                break
            if not best_match: 
                best_match = ben
    if best_match:
        current_val = entry_voucher_beneficiary.get().strip()
        if not current_val:
            entry_voucher_beneficiary.set(best_match)

# ===================== ADD WINDOWS (Popup Functions) =====================

# 1. Add Beneficiary Popup
def open_add_beneficiary_window():
    popup = tk.Toplevel(root)
    popup.title("Add New Beneficiary")
    popup.geometry("400x150")
    
    x = root.winfo_x() + (root.winfo_width() // 2) - 200
    y = root.winfo_y() + (root.winfo_height() // 2) - 75
    popup.geometry(f"+{x}+{y}")

    tk.Label(popup, text="Enter New Beneficiary Name:", font=("Helvetica", 10)).pack(pady=10)
    new_ben_entry = tk.Entry(popup, font=("Helvetica", 11), width=30)
    new_ben_entry.pack(pady=5)
    new_ben_entry.focus_set()

    def save_new_beneficiary():
        new_name = new_ben_entry.get().strip()
        if not new_name:
            messagebox.showwarning("Warning", "Name cannot be empty.", parent=popup)
            return
        
        if any(b.lower() == new_name.lower() for b in beneficiaries_list):
            messagebox.showinfo("Info", "This beneficiary already exists.", parent=popup)
            entry_voucher_beneficiary.set(new_name)
            popup.destroy()
            return

        beneficiaries_list.append(new_name)
        entry_voucher_beneficiary.set_completion_list(beneficiaries_list)
        entry_voucher_beneficiary.set(new_name)
        popup.destroy()

    tk.Button(popup, text="Save & Select", command=save_new_beneficiary, bg="#4CAF50", fg="white").pack(pady=10)
    popup.bind('<Return>', lambda event: save_new_beneficiary())

# 2. Add Supplier Popup
def open_add_supplier_window():
    popup = tk.Toplevel(root)
    popup.title("Add New Supplier")
    popup.geometry("400x200")
    
    x = root.winfo_x() + (root.winfo_width() // 2) - 200
    y = root.winfo_y() + (root.winfo_height() // 2) - 100
    popup.geometry(f"+{x}+{y}")

    tk.Label(popup, text="NIF Code:", font=("Helvetica", 10)).pack(pady=(15, 2))
    entry_nif = tk.Entry(popup, font=("Helvetica", 11), width=30)
    entry_nif.pack(pady=2)

    tk.Label(popup, text="Supplier Name:", font=("Helvetica", 10)).pack(pady=(10, 2))
    entry_name = tk.Entry(popup, font=("Helvetica", 11), width=30)
    entry_name.pack(pady=2)
    entry_nif.focus_set()

    def save_new_supplier():
        nif_code = entry_nif.get().strip()
        supplier_name = entry_name.get().strip()

        if not nif_code or not supplier_name:
            messagebox.showwarning("Input Error", "Please fill both NIF Code and Name.", parent=popup)
            return

        try:
            conn = mysql.connector.connect(**db_config)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM NIF_Codes WHERE Supplier_Name = %s OR Supplier_NIF_Code = %s", (supplier_name, nif_code))
            if cur.fetchone():
                messagebox.showerror("Error", "Supplier Name or NIF already exists.", parent=popup)
                return

            insert_query = "INSERT INTO NIF_Codes (Supplier_NIF_Code, Supplier_Name) VALUES (%s, %s)"
            cur.execute(insert_query, (nif_code, supplier_name))
            conn.commit()
            
            new_id = cur.lastrowid
            global suppliers
            suppliers.append((new_id, supplier_name))
            supplier_id_map[supplier_name] = new_id
            
            updated_names = [s[1] for s in suppliers]
            supplier_dropdown.set_completion_list(updated_names)
            supplier_dropdown.set(supplier_name)

            messagebox.showinfo("Success", f"Supplier added!\nID: {new_id}", parent=popup)
            popup.destroy()

        except Error as e:
            messagebox.showerror("Database Error", f"Error: {e}", parent=popup)
        finally:
            if 'conn' in locals() and conn.is_connected():
                cur.close(); conn.close()

    btn_save = tk.Button(popup, text="Add Supplier", command=save_new_supplier, bg="#4CAF50", fg="white")
    btn_save.pack(pady=15)
    popup.bind('<Return>', lambda event: save_new_supplier())

# ===================== Invoice List Logic =========================
invoices_list = []

def add_invoice_to_list():
    supplier_name = supplier_var.get().strip()
    invoice_number = invoice_number_entry.get().strip()
    invoice_date = invoice_date_entry.get().strip()
    invoice_amount = invoice_amount_entry.get().strip()
    invoice_vat = invoice_vat_entry.get().strip()
    refundable = vat_refundable_var.get()
    status = status_var.get().strip()
    recurring = recurring_var.get()

    if not all([supplier_name, invoice_number, invoice_date, invoice_amount, invoice_vat, refundable, status, recurring]):
        status_label.config(text="Please fill in all required invoice fields.", fg="red")
        return
    try:
        invoice_amount = Decimal(invoice_amount)
        invoice_vat = Decimal(invoice_vat) if invoice_vat else Decimal('0.00')
    except ValueError:
        messagebox.showwarning("Input Error", "Invoice Amount and VAT must be numbers.")
        return
    try:
        datetime.strptime(invoice_date, '%Y-%m-%d')
    except ValueError:
        messagebox.showwarning("Input Error", "Invalid date format. Use YYYY-MM-DD.")
        return

    supplier_id = supplier_id_map.get(supplier_name)
    if not supplier_id:
        messagebox.showwarning("Input Error", f"Supplier '{supplier_name}' not found.")
        return
    
    for inv in invoices_list:
        if (inv["supplier_name"] == supplier_name and inv["invoice_number"] == invoice_number and 
            inv["invoice_amount"] == invoice_amount):
            messagebox.showinfo("Duplicate Invoice", "This invoice has already been entered during this session.")
            return
    
    inv = {
        "supplier_name": supplier_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "invoice_amount": invoice_amount,
        "invoice_vat": invoice_vat,
        "refundable": refundable,
        "status": status,
        "recurring": recurring
    }
    
    invoices_list.append(inv)
    invoices_tree.insert("", "end", values=(
        supplier_name, invoice_number, invoice_date, f"{invoice_amount:.2f}", f"{invoice_vat:.2f}", refundable, recurring, status
    ))
    
    update_voucher_euro_default()
    
    # Clear Invoice Fields
    supplier_var.set('')
    invoice_number_entry.delete(0, tk.END)
    invoice_date_entry.delete(0, tk.END)
    invoice_date_entry.insert(0, date.today().strftime('%Y-%m-%d'))
    invoice_amount_entry.delete(0, tk.END)
    invoice_vat_entry.delete(0, tk.END)
    vat_refundable_var.set(1)
    status_var.set(DEFAULT_STATUS)
    vat_0_var.set(0)
    vat_10_var.set(0)
    vat_21_var.set(0)
    invoice_vat_entry.config(state='normal')
    supplier_dropdown.focus_set()

def remove_selected_invoice():
    sel = invoices_tree.selection()
    if not sel:
        return
    for iid in sel:
        vals = invoices_tree.item(iid, "values")
        for idx, inv in enumerate(invoices_list):
            if (str(inv["supplier_name"]) == str(vals[0]) and
                str(inv["invoice_number"]) == str(vals[1]) and
                f"{(inv['invoice_amount']):.2f}" == str(vals[3])):
                invoices_list.pop(idx)
                break
        invoices_tree.delete(iid)
        update_voucher_euro_default()

# ===================== Voucher List Logic =====================
vouchers_list = []

def add_voucher_to_list():
    number_raw = entry_voucher_number.get().strip()
    beneficiary = entry_voucher_beneficiary.get().strip()
    euro_s = entry_voucher_euro.get().strip()
    quarter_s = entry_voucher_quarter.get().strip()
    year_s = entry_voucher_year.get().strip()
    head_name = budget_head_var.get().strip()

    if not all([number_raw, beneficiary, euro_s, quarter_s, year_s, head_name]):
        messagebox.showwarning("Input Error", "Please fill all voucher fields.")
        return
    try:
        euro = Decimal(euro_s)
        quarter = int(quarter_s)
        year = int(year_s)
    except ValueError:
        messagebox.showwarning("Input Error", "Invalid numeric input in voucher fields.")
        return
    if head_name not in budget_heads:
        messagebox.showwarning("Input Error", f"Budget head '{head_name}' not found.")
        return

    number = pad_voucher_number(number_raw)

    for v in vouchers_list:
        if v["number"] == number and v["beneficiary"] == beneficiary:
            messagebox.showinfo("Duplicate", "This voucher entry is already in the list.")
            return

    v = {
        "number": number,
        "beneficiary": beneficiary,
        "euro": euro,
        "quarter": quarter,
        "year": year,
        "head_name": head_name
    }
    vouchers_list.append(v)
    vouchers_tree.insert("", "end", values=(
        number, beneficiary, f"{euro:.2f}", quarter, year, head_name
    ))

    # Clear fields but keep context
    entry_voucher_number.delete(0, tk.END)
    entry_voucher_beneficiary.delete(0, tk.END)
    entry_voucher_quarter.delete(0, tk.END)
    entry_voucher_year.delete(0, tk.END)
    budget_head_var.set(DEFAULT_HEAD)

def remove_selected_voucher():
    sel = vouchers_tree.selection()
    if not sel:
        return
    for iid in sel:
        vals = vouchers_tree.item(iid, "values")
        for idx, v in enumerate(vouchers_list):
            if str(v["number"]) == str(vals[0]):
                vouchers_list.pop(idx)
                break
        vouchers_tree.delete(iid)

# ===================== NEW FUNCTION: Submit Voucher Only =====================
def submit_voucher_only():
    """Reads directly from the Voucher Input boxes and saves to DB without invoices."""
    number_raw = entry_voucher_number.get().strip()
    beneficiary = entry_voucher_beneficiary.get().strip()
    euro_s = entry_voucher_euro.get().strip()
    quarter_s = entry_voucher_quarter.get().strip()
    year_s = entry_voucher_year.get().strip()
    head_name = budget_head_var.get().strip()

    if not all([number_raw, beneficiary, euro_s, quarter_s, year_s, head_name]):
        messagebox.showwarning("Input Error", "Please fill all voucher fields to submit.")
        return
    
    try:
        euro = Decimal(euro_s)
        quarter = int(quarter_s)
        year = int(year_s)
        head_id = budget_heads.get(head_name)
    except ValueError:
        messagebox.showwarning("Input Error", "Invalid numeric input.")
        return
    
    if not head_id:
        messagebox.showwarning("Input Error", "Invalid Budget Head.")
        return

    number = pad_voucher_number(number_raw)

    if messagebox.askyesno("Confirm", f"Submit Voucher #{number} ONLY?\n(No invoices will be linked)"):
        try:
            conn = mysql.connector.connect(**db_config)
            cur = conn.cursor()
            
            # Check duplicate
            cur.execute("SELECT 1 FROM Vouchers WHERE Voucher_Number = %s", (number,))
            if cur.fetchone():
                messagebox.showerror("Duplicate", f"Voucher {number} already exists in Database.")
                return

            sql = """INSERT INTO Vouchers 
                     (Voucher_Number, Head_of_Accounts_ID, Voucher_Beneficiary, Voucher_Euro, Voucher_Quarter, Voucher_Year)
                     VALUES (%s, %s, %s, %s, %s, %s)"""
            cur.execute(sql, (number, head_id, beneficiary, euro, quarter, year))
            conn.commit()
            
            messagebox.showinfo("Success", f"Voucher {number} inserted successfully.")
            
            # Clear fields
            entry_voucher_number.delete(0, tk.END)
            entry_voucher_beneficiary.delete(0, tk.END)
            entry_voucher_euro.delete(0, tk.END)
            entry_voucher_euro.insert(0, "0.00")
            entry_voucher_quarter.delete(0, tk.END)
            entry_voucher_year.delete(0, tk.END)
            budget_head_var.set(DEFAULT_HEAD)

        except Error as e:
            messagebox.showerror("Database Error", f"Error: {e}")
        finally:
            if 'conn' in locals() and conn.is_connected():
                cur.close(); conn.close()

# ===================== Event Handlers =====================
def submit_transaction():
    office = office_var.get()
    table_name = "Invoices_Chancery" if office == "Chancery" else "Invoices_Residence"
    link_table = "Vouchers_Chancery" if office == "Chancery" else "Vouchers_Residence"
    
    invoice_ids = []
    voucher_ids = []

    if not invoices_list and not vouchers_list:
        messagebox.showwarning("Empty", "No invoices or vouchers to submit.")
        return

    if len(invoices_list) > 1 and len(vouchers_list) > 1:
        messagebox.showwarning("Input Error", "Cannot submit multiple invoices AND multiple vouchers.")
        return

    try:
        conn = mysql.connector.connect(**db_config)
        cur = conn.cursor()

        for i in invoices_list:
            cur.execute(f"SELECT 1 FROM {table_name} WHERE Number = %s", (i["invoice_number"],))
            if cur.fetchone():
                messagebox.showerror("Duplicate Invoice", f"Invoice {i['invoice_number']} already exists.")
                return

        for i in invoices_list: 
            supp_id = supplier_id_map.get(i["supplier_name"])
            cur.execute(f"""INSERT INTO {table_name}
            (Supplier_ID, Number, Date, Total, Vat, Refundable, Status, Recurring)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (supp_id, i["invoice_number"], i["invoice_date"], i["invoice_amount"], i["invoice_vat"],
             i["refundable"], i["status"], i["recurring"])
            )
            invoice_ids.append(cur.lastrowid)

        for v in vouchers_list:
            head_id = budget_heads.get(v["head_name"])
            cur.execute(
                """INSERT INTO Vouchers
                   (Voucher_Number, Head_of_Accounts_ID, Voucher_Beneficiary, Voucher_Euro, Voucher_Quarter, Voucher_Year)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (v["number"], head_id, v["beneficiary"], v["euro"], v["quarter"], v["year"])
            )
            voucher_id = cur.lastrowid
            voucher_ids.append(voucher_id)

            for inv_id in invoice_ids:
                cur.execute(
                    f"INSERT INTO {link_table} (Invoice_ID, Voucher_ID) VALUES (%s, %s)",
                    (inv_id, voucher_id)
                )

        conn.commit()
        messagebox.showinfo("Success", f"Transaction Successful. Linked {len(voucher_ids)} vouchers.")
        status_label.config(text="Transaction Submitted.", fg="green")
        clear_form()

    except Error as e:
        messagebox.showerror("Database Error", f"Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cur.close(); conn.close()

def clear_form():
    supplier_var.set('')
    invoice_number_entry.delete(0, tk.END)
    invoice_date_entry.delete(0, tk.END)
    invoice_date_entry.insert(0, date.today().strftime('%Y-%m-%d'))
    invoice_amount_entry.delete(0, tk.END)
    invoice_vat_entry.delete(0, tk.END)
    vat_refundable_var.set(1)
    status_var.set(DEFAULT_STATUS)
    vat_0_var.set(0)
    vat_10_var.set(0)
    vat_21_var.set(0)
    invoice_vat_entry.config(state='normal')
    recurring_var.set(1)
    status_label.config(text="", fg="black")

    entry_voucher_number.delete(0, tk.END)
    entry_voucher_beneficiary.delete(0, tk.END)
    entry_voucher_euro.delete(0, tk.END)
    entry_voucher_quarter.delete(0, tk.END)
    entry_voucher_year.delete(0, tk.END)
    budget_head_var.set(DEFAULT_HEAD)

    vouchers_list.clear()
    for child in vouchers_tree.get_children():
        vouchers_tree.delete(child)
    supplier_dropdown.focus_set()

def on_vat_checkbox_change(rate):
    if rate == 21 and vat_21_var.get():
        vat_10_var.set(0)
        vat_0_var.set(0)
    elif rate == 10 and vat_10_var.get():
        vat_21_var.set(0)
        vat_0_var.set(0)
    elif rate == 0 and vat_0_var.get():
        vat_21_var.set(0)
        vat_10_var.set(0)
    calc_vat_from_ui()

def calc_vat_from_ui():
    rate = 0
    if vat_21_var.get(): rate = 21
    elif vat_10_var.get(): rate = 10
    
    if not (vat_21_var.get() or vat_10_var.get() or vat_0_var.get()):
        invoice_vat_entry.config(state='normal')
        return

    try:
        total = Decimal(invoice_amount_entry.get())
        vat = calculate_vat_generic(total, rate)
        invoice_vat_entry.config(state='normal')
        invoice_vat_entry.delete(0, tk.END)
        invoice_vat_entry.insert(0, f"{vat:.2f}")
        invoice_vat_entry.config(state='readonly')
        invoice_vat_var.set(f"{vat:.2f}")
    except:
        pass

def on_invoice_amount_change(*args):
    calc_vat_from_ui()

def batch_insert():
    pass 

# ===================== Data =====================
suppliers = fetch_suppliers()
supplier_id_map = {supplier[1]: supplier[0] for supplier in suppliers}
budget_heads = fetch_budget_heads()
beneficiaries_list = fetch_beneficiaries()

# ===================== GUI =====================
root = tk.Tk()
root.title("Invoice Entry Form")
root.geometry("900x750")

label_font = ("Helvetica", 10)
button_font = ("Helvetica", 10, "bold")
root.columnconfigure(1, weight=1)
root.columnconfigure(3, weight=1)

PAD_X = 5
PAD_Y = 2

tk.Label(root, text="Office:", font=label_font).grid(row=0, column=0, padx=PAD_X, pady=10, sticky="e")
office_frame = tk.Frame(root)
office_frame.grid(row=0, column=1, columnspan=3, sticky="w", padx=PAD_X, pady=5)
office_var = tk.StringVar(value=DEFAULT_OFFICE)
tk.Radiobutton(office_frame, text="Chancery", variable=office_var, value="Chancery", font=label_font).pack(side="left", padx=10)
tk.Radiobutton(office_frame, text="Residence", variable=office_var, value="Residence", font=label_font).pack(side="left", padx=10)

# Invoice Details
tk.Label(root, text="Supplier:", font=label_font).grid(row=1, column=0, padx=PAD_X, pady=PAD_Y, sticky="e")

# Supplier Row with Add Button
supplier_var = tk.StringVar()
supp_frame = tk.Frame(root)
supp_frame.grid(row=1, column=1, padx=PAD_X, pady=PAD_Y, sticky="ew")

supplier_dropdown = AutocompleteCombobox(supp_frame, textvariable=supplier_var, font=label_font)
supplier_dropdown.set_completion_list([supplier[1] for supplier in suppliers])
supplier_dropdown.pack(side="left", fill="x", expand=True)
supplier_var.trace_add("write", auto_suggest_beneficiary)

btn_add_supp = tk.Button(supp_frame, text="+", width=3, command=open_add_supplier_window, bg="#ddd")
btn_add_supp.pack(side="right", padx=(5, 0))

tk.Label(root, text="Invoice Number:", font=label_font).grid(row=1, column=2, padx=PAD_X, pady=PAD_Y, sticky="e")
invoice_number_entry = tk.Entry(root, font=label_font)
invoice_number_entry.grid(row=1, column=3, padx=PAD_X, pady=PAD_Y, sticky="ew")

tk.Label(root, text="Date (YYYY-MM-DD):", font=label_font).grid(row=2, column=0, padx=PAD_X, pady=PAD_Y, sticky="e")
invoice_date_entry = tk.Entry(root, font=label_font)
invoice_date_entry.grid(row=2, column=1, padx=PAD_X, pady=PAD_Y, sticky="ew")
invoice_date_entry.insert(0, date.today().strftime('%Y-%m-%d'))

tk.Label(root, text="Amount (€):", font=label_font).grid(row=2, column=2, padx=PAD_X, pady=PAD_Y, sticky="e")
invoice_amount_var = tk.StringVar()
invoice_amount_entry = tk.Entry(root, textvariable=invoice_amount_var, font=label_font)
invoice_amount_entry.grid(row=2, column=3, padx=PAD_X, pady=PAD_Y, sticky="ew")
invoice_amount_var.trace_add('write', on_invoice_amount_change)

# VAT
vat_frame = tk.Frame(root)
vat_frame.grid(row=3, column=0, columnspan=4, pady=5)
vat_0_var = tk.IntVar()
tk.Checkbutton(vat_frame, text="VAT 0%", variable=vat_0_var, font=label_font, 
               command=lambda: on_vat_checkbox_change(0)).pack(side="left", padx=10)
vat_10_var = tk.IntVar()
tk.Checkbutton(vat_frame, text="VAT 10%", variable=vat_10_var, font=label_font, 
               command=lambda: on_vat_checkbox_change(10)).pack(side="left", padx=10)
vat_21_var = tk.IntVar()
tk.Checkbutton(vat_frame, text="VAT 21%", variable=vat_21_var, font=label_font, 
               command=lambda: on_vat_checkbox_change(21)).pack(side="left", padx=10)

tk.Label(root, text="VAT (€):", font=label_font).grid(row=4, column=0, padx=PAD_X, pady=PAD_Y, sticky="e")
invoice_vat_var = tk.StringVar()
invoice_vat_entry = tk.Entry(root, textvariable=invoice_vat_var, font=label_font)
invoice_vat_entry.grid(row=4, column=1, padx=PAD_X, pady=PAD_Y, sticky="ew")

tk.Label(root, text="Status:", font=label_font).grid(row=4, column=2, padx=PAD_X, pady=PAD_Y, sticky="e")
status_var = tk.StringVar(value=DEFAULT_STATUS)
status_dropdown = ttk.Combobox(root, textvariable=status_var, font=label_font, state="readonly", values=["Pending", "Processed", "Archived"])
status_dropdown.grid(row=4, column=3, padx=PAD_X, pady=PAD_Y, sticky="ew")

flags_frame = tk.Frame(root)
flags_frame.grid(row=5, column=1, columnspan=3, sticky="w", pady=PAD_Y)
vat_refundable_var = tk.IntVar(value=1)
tk.Checkbutton(flags_frame, text="Refundable", variable=vat_refundable_var, font=label_font).pack(side="left", padx=5)
recurring_var = tk.IntVar(value=1)
tk.Checkbutton(flags_frame, text="Recurring", variable=recurring_var, font=label_font).pack(side="left", padx=20)

btn_add_invoice = tk.Button(root, text="Add Invoice", command=add_invoice_to_list, font=button_font, bg="#6A5ACD", fg="white")
btn_add_invoice.grid(row=6, column=0, columnspan=4, pady=10)

cols = ("Supplier", "Invoice Number", "Date", "Amount (€)", "VAT (€)", "Refundable", "Recurring", "Status")
invoices_tree = ttk.Treeview(root, columns=cols, show="headings", height=5)
for c in cols:
    invoices_tree.heading(c, text=c)
    invoices_tree.column(c, width=90, anchor="w")
invoices_tree.grid(row=7, column=0, columnspan=4, padx=10, pady=5, sticky="nsew")

btn_remove_invoice = tk.Button(root, text="Remove Selected", command=remove_selected_invoice, font=("Helvetica", 9), bg="#B22222", fg="white")
btn_remove_invoice.grid(row=8, column=0, padx=10, pady=5, sticky="w")

# Vouchers
ttk.Separator(root, orient='horizontal').grid(row=9, column=0, columnspan=4, sticky="ew", padx=10, pady=10)
tk.Label(root, text="Voucher Entry:", font=("Helvetica", 11, "bold")).grid(row=10, column=0, columnspan=4, pady=5)

tk.Label(root, text="Voucher #:", font=label_font).grid(row=11, column=0, padx=PAD_X, pady=PAD_Y, sticky="e")
entry_voucher_number = tk.Entry(root, font=label_font)
entry_voucher_number.grid(row=11, column=1, padx=PAD_X, pady=PAD_Y, sticky="ew")
entry_voucher_number.bind("<KeyRelease>", on_voucher_number_change)

# Beneficiary Row with Add Button
tk.Label(root, text="Beneficiary:", font=label_font).grid(row=11, column=2, padx=PAD_X, pady=PAD_Y, sticky="e")
ben_frame = tk.Frame(root)
ben_frame.grid(row=11, column=3, padx=PAD_X, pady=PAD_Y, sticky="ew")

entry_voucher_beneficiary = AutocompleteCombobox(ben_frame, font=label_font)
entry_voucher_beneficiary.set_completion_list(beneficiaries_list)
entry_voucher_beneficiary.pack(side="left", fill="x", expand=True)

btn_add_ben = tk.Button(ben_frame, text="+", width=3, command=open_add_beneficiary_window, bg="#ddd")
btn_add_ben.pack(side="right", padx=(5, 0))

tk.Label(root, text="Euro (€):", font=label_font).grid(row=12, column=0, padx=PAD_X, pady=PAD_Y, sticky="e")
entry_voucher_euro = tk.Entry(root, font=label_font)
entry_voucher_euro.grid(row=12, column=1, padx=PAD_X, pady=PAD_Y, sticky="ew")
entry_voucher_euro.insert(0, "0.00")

tk.Label(root, text="Budget Head:", font=label_font).grid(row=12, column=2, padx=PAD_X, pady=PAD_Y, sticky="e")
budget_head_var = tk.StringVar(value=DEFAULT_HEAD)
budget_head_dropdown = AutocompleteCombobox(root, textvariable=budget_head_var, font=label_font)
budget_head_dropdown.set_completion_list(list(budget_heads.keys()))
budget_head_dropdown.grid(row=12, column=3, padx=PAD_X, pady=PAD_Y, sticky="ew")

tk.Label(root, text="Quarter:", font=label_font).grid(row=13, column=0, padx=PAD_X, pady=PAD_Y, sticky="e")
entry_voucher_quarter = tk.Entry(root, font=label_font)
entry_voucher_quarter.grid(row=13, column=1, padx=PAD_X, pady=PAD_Y, sticky="ew")

tk.Label(root, text="Year:", font=label_font).grid(row=13, column=2, padx=PAD_X, pady=PAD_Y, sticky="e")
entry_voucher_year = tk.Entry(root, font=label_font)
entry_voucher_year.grid(row=13, column=3, padx=PAD_X, pady=PAD_Y, sticky="ew")

btn_add_voucher = tk.Button(root, text="Add Voucher (To List)", command=add_voucher_to_list, font=button_font, bg="#6A5ACD", fg="white")
btn_add_voucher.grid(row=14, column=0, columnspan=4, pady=10)

vcols = ("Number", "Beneficiary", "Euro", "Quarter", "Year", "Budget Head")
vouchers_tree = ttk.Treeview(root, columns=vcols, show="headings", height=4)
for c in vcols:
    vouchers_tree.heading(c, text=c)
    vouchers_tree.column(c, width=100, anchor="w")
vouchers_tree.grid(row=15, column=0, columnspan=4, padx=10, pady=5, sticky="nsew")

btn_remove_voucher = tk.Button(root, text="Remove Selected", command=remove_selected_voucher, font=("Helvetica", 9), bg="#B22222", fg="white")
btn_remove_voucher.grid(row=16, column=0, padx=10, pady=5, sticky="w")

# SUBMIT BUTTONS
button_frame = tk.Frame(root)
button_frame.grid(row=17, column=0, columnspan=4, pady=20)

# 1. Main Transaction
submit_button = tk.Button(button_frame, text="SUBMIT TRANSACTION\n(Link Invoices & Vouchers)", command=submit_transaction, font=button_font, bg="#4CAF50", fg="white", width=25)
submit_button.pack(side="left", padx=20)

# 2. Separate Voucher Only
btn_submit_voucher_only = tk.Button(button_frame, text="SUBMIT VOUCHER ONLY\n(No Invoices)", command=submit_voucher_only, font=button_font, bg="#FFA500", fg="white", width=20)
btn_submit_voucher_only.pack(side="left", padx=20)


ttk.Separator(root, orient='horizontal').grid(row=18, column=0, columnspan=4, sticky="ew", padx=10)
batch_insert_button = tk.Button(root, text="Batch Insert CSV", command=batch_insert, font=("Helvetica", 10), bg="#2196F3", fg="white")
batch_insert_button.grid(row=19, column=0, columnspan=4, pady=10)

status_label = tk.Label(root, text="", font=label_font, fg="red")
status_label.grid(row=20, column=0, columnspan=4, sticky="w", padx=10)

root.grid_rowconfigure(7, weight=1)
root.grid_rowconfigure(15, weight=1)

root.mainloop()