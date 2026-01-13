#!/usr/bin/env python3
import os
from contextlib import contextmanager
from db import get_cnx  # central DB connector
import tkinter as tk
from tkinter import ttk, messagebox
from mysql.connector import Error
from datetime import datetime

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
    """
    A Combobox with autocompletion.
    """
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
        if matches:
            self['values'] = matches
            self.event_generate('<Down>')
        else:
            self['values'] = self._completion_list

    def _handle_selected(self, event):
        pass

# ==========================================================
# Database Fetch Function
# ==========================================================
def fetch_data_from_db():
    try:
        with db_cursor(commit=False) as cur:
            # Fetch colleagues: only rank_id between 1 and 5 and ordered by rank_id
            cur.execute("SELECT Colleague_ID, Colleague_Name FROM Colleagues WHERE rank_id BETWEEN 1 AND 5 ORDER BY rank_id")
            colleagues = cur.fetchall()
            cur.execute("SELECT recipient_id, Name FROM Recipients")
            recipients = cur.fetchall()
            cur.execute("SELECT Supplier_ID, Supplier_Name FROM NIF_Codes")
            suppliers = cur.fetchall()
            cur.execute("SELECT Refund_Status_ID, Refund_Status_Type FROM Refund_Status")
            refund_statuses = cur.fetchall()
            return colleagues, recipients, suppliers, refund_statuses
    except Error as e:
        messagebox.showerror("Database Error", f"Error fetching data: {e}")
        return [], [], [], []
# ==========================================================
# Event Handlers
# ==========================================================
def submit_transaction():
    store_name = store_var.get()
    colleague_name = colleague_var.get()
    recipient_name = recipient_var.get()
    invoice_number = invoice_number_entry.get().strip()
    invoice_date = invoice_date_entry.get().strip()
    invoice_amount = invoice_amount_entry.get().strip()
    invoice_vat = invoice_vat_entry.get().strip()
    refund_status_name = refund_status_var.get()
    date_refunded = date_refunded_entry.get().strip()

    if not all([store_name, colleague_name, recipient_name, invoice_number, invoice_date, invoice_amount, invoice_vat, refund_status_name]):
        messagebox.showwarning("Input Error", "Please fill in all required fields.")
        return

    try:
        invoice_amount = float(invoice_amount)
        invoice_vat = float(invoice_vat)
    except ValueError:
        messagebox.showwarning("Input Error", "Invoice Amount and VAT must be numbers.")
        return

    for date_str, field_name in [(invoice_date, "Invoice Date"), (date_refunded, "Date Refunded")]:
        if date_str:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                messagebox.showwarning("Input Error", f"Invalid date format for {field_name}: {date_str}. Use YYYY-MM-DD.")
                return

    store_id = supplier_id_map.get(store_name)
    Colleague_ID = Colleague_ID_map.get(colleague_name)
    recipient_id = recipient_id_map.get(recipient_name)
    refund_status_id = refund_status_id_map.get(refund_status_name)

    try:
        with db_cursor(commit=True) as cur:
            cur.execute("SELECT * FROM Invoices_Personal WHERE Number = %s", (invoice_number,))
            invoice = cur.fetchone()
            if invoice:
                messagebox.showerror("Duplicate Invoice", "An invoice with this number already exists.")
                return

            query = """
            INSERT INTO Invoices_Personal (Store, Colleague_ID, Recipient_ID, Number, Date, Amount, VAT, Status, Date_Refunded)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cur.execute(query, (
                store_id,
                Colleague_ID,
                recipient_id,
                invoice_number,
                invoice_date,
                invoice_amount,
                invoice_vat,
                refund_status_id,
                date_refunded if date_refunded else None
            ))
            print("Store ID:", store_id)
            print("Colleague ID:", Colleague_ID)
            print("Recipient ID:", recipient_id)
            print("Refund Status ID:", refund_status_id)
            messagebox.showinfo("Success", "Invoice submitted successfully.")
            clear_form()
    except Error as e:
        messagebox.showerror("Database Error", f"Error submitting invoice: {e}")
def clear_form():
    store_var.set('')
    colleague_var.set('')
    recipient_var.set('')
    invoice_number_entry.delete(0, tk.END)
    invoice_date_entry.delete(0, tk.END)
    invoice_amount_entry.delete(0, tk.END)
    invoice_vat_entry.delete(0, tk.END)
    refund_status_var.set('')
    date_refunded_entry.delete(0, tk.END)
    vat_21_var.set(0)

def on_colleague_select(event):
    selected_colleague = colleague_var.get()
    if selected_colleague:
        recipient_var.set(selected_colleague)

def on_vat_checkbox_toggle():
    if vat_21_var.get():
        try:
            total_amount = float(invoice_amount_entry.get())
            vat = calculate_vat_from_total(total_amount)
            invoice_vat_entry.delete(0, tk.END)
            invoice_vat_entry.insert(0, f"{vat:.2f}")
            invoice_vat_entry.config(state='readonly')
        except ValueError:
            messagebox.showwarning("Input Error", "Please enter a valid Invoice Amount before calculating VAT.")
            vat_21_var.set(0)
    else:
        invoice_vat_entry.config(state='normal')

def calculate_vat_from_total(total_amount):
    return total_amount * 21 / 121

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
colleagues, recipients, suppliers, refund_statuses = fetch_data_from_db()

Colleague_ID_map = {colleague[1]: colleague[0] for colleague in colleagues}
recipient_id_map = {recipient[1]: recipient[0] for recipient in recipients}
supplier_id_map = {supplier[1]: supplier[0] for supplier in suppliers}
refund_status_id_map = {status[1]: status[0] for status in refund_statuses}

# ==========================================================
# Tkinter GUI Setup
# ==========================================================
root = tk.Tk()
root.title("Personal Invoice Entry Form")
root.geometry("700x600")
root.configure(bg="#E8F0FE")
for widget in root.winfo_children():
    try:
        widget.configure(bg="#E8F0FE")
    except:
        pass

root.update_idletasks()
w = root.winfo_width()
h = root.winfo_height()
ws = root.winfo_screenwidth()
hs = root.winfo_screenheight()
x = (ws // 2) - (w // 2)
y = (hs // 2) - (h // 2)
root.geometry(f"{w}x{h}+{x}+{y}")

padding_options = {'padx': 10, 'pady': 5}

tk.Label(root, text="Store:", font=("Helvetica", 12), bg="#E8F0FE").grid(row=0, column=0, sticky=tk.E, **padding_options)
store_var = tk.StringVar()
store_dropdown = AutocompleteCombobox(root, textvariable=store_var, state="readonly", font=("Helvetica", 12), width=30)
store_dropdown.set_completion_list([supplier[1] for supplier in suppliers])
store_dropdown.grid(row=0, column=1, **padding_options)

tk.Label(root, text="Colleague:", font=("Helvetica", 12), bg="#E8F0FE").grid(row=1, column=0, sticky=tk.E, **padding_options)
colleague_var = tk.StringVar()
colleague_dropdown = AutocompleteCombobox(root, textvariable=colleague_var, state="readonly", font=("Helvetica", 12), width=30)
colleague_dropdown.set_completion_list([colleague[1] for colleague in colleagues])
colleague_dropdown.grid(row=1, column=1, **padding_options)
colleague_dropdown.bind("<<ComboboxSelected>>", on_colleague_select)

tk.Label(root, text="Recipient:", font=("Helvetica", 12), bg="#E8F0FE").grid(row=2, column=0, sticky=tk.E, **padding_options)
recipient_var = tk.StringVar()
recipient_dropdown = AutocompleteCombobox(root, textvariable=recipient_var, state="readonly", font=("Helvetica", 12), width=30)
recipient_dropdown.set_completion_list([recipient[1] for recipient in recipients])
recipient_dropdown.grid(row=2, column=1, **padding_options)

tk.Label(root, text="Invoice Number:", font=("Helvetica", 12), bg="#E8F0FE").grid(row=3, column=0, sticky=tk.E, **padding_options)
invoice_number_entry = tk.Entry(root, font=("Helvetica", 12), width=32)
invoice_number_entry.grid(row=3, column=1, **padding_options)

tk.Label(root, text="Invoice Date (YYYY-MM-DD):", font=("Helvetica", 12), bg="#E8F0FE").grid(row=4, column=0, sticky=tk.E, **padding_options)
invoice_date_entry = tk.Entry(root, font=("Helvetica", 12), width=32)
invoice_date_entry.grid(row=4, column=1, **padding_options)

tk.Label(root, text="Invoice Amount (€):", font=("Helvetica", 12), bg="#E8F0FE").grid(row=5, column=0, sticky=tk.E, **padding_options)
invoice_amount_var = tk.StringVar()
invoice_amount_entry = tk.Entry(root, textvariable=invoice_amount_var, font=("Helvetica", 12), width=32)
invoice_amount_entry.grid(row=5, column=1, **padding_options)
invoice_amount_var.trace_add('write', on_invoice_amount_change)

vat_21_var = tk.IntVar()
vat_checkbox = tk.Checkbutton(root, text="Is VAT 21%?", variable=vat_21_var, font=("Helvetica", 12), command=on_vat_checkbox_toggle, bg="#E8F0FE")
vat_checkbox.grid(row=6, column=0, sticky=tk.E, **padding_options)

tk.Label(root, text="Invoice VAT (€):", font=("Helvetica", 12), bg="#E8F0FE").grid(row=6, column=1, sticky=tk.W, **padding_options)
invoice_vat_var = tk.StringVar()
invoice_vat_entry = tk.Entry(root, textvariable=invoice_vat_var, font=("Helvetica", 12), width=32)
invoice_vat_entry.grid(row=6, column=1, sticky=tk.E, **padding_options)

tk.Label(root, text="Refund Status:", font=("Helvetica", 12), bg="#E8F0FE").grid(row=7, column=0, sticky=tk.E, **padding_options)
refund_status_var = tk.StringVar()
refund_status_dropdown = AutocompleteCombobox(root, textvariable=refund_status_var, state="readonly", font=("Helvetica", 12), width=30)
refund_status_dropdown.set_completion_list([status[1] for status in refund_statuses])
refund_status_dropdown.grid(row=7, column=1, **padding_options)

tk.Label(root, text="Date Refunded (YYYY-MM-DD, optional):", font=("Helvetica", 12), bg="#E8F0FE").grid(row=8, column=0, sticky=tk.E, **padding_options)
date_refunded_entry = tk.Entry(root, font=("Helvetica", 12), width=32)
date_refunded_entry.grid(row=8, column=1, **padding_options)

submit_button = tk.Button(root, text="Submit", command=submit_transaction, font=("Helvetica", 12), bg="#4CAF50", fg="white", width=15)
submit_button.grid(row=9, column=1, sticky=tk.E, **padding_options)

root.mainloop()
