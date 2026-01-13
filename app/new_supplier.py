#!/usr/bin/env python3
import tkinter as tk
from tkinter import messagebox
from contextlib import contextmanager
from mysql.connector import Error
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
# Function to add supplier to database and retrieve new Supplier_ID
# ==========================================================
def add_supplier( nif_code, supplier_name):
    try:
        with db_cursor(commit=True) as cur:
            insert_query = """
            INSERT INTO administration.NIF_Codes (Supplier_NIF_Code, Supplier_Name)
            VALUES (%s, %s)
            """
            cur.execute(insert_query, (nif_code, supplier_name))
        
            # Retrieve the last inserted Supplier_ID
            new_supplier_id = cur.lastrowid
            messagebox.showinfo("Success", f"Supplier added successfully with ID: {new_supplier_id}")
    except Error as e:
        messagebox.showerror("Error", f"Error: {e}")

# ==========================================================
# Function to handle button click event
# ==========================================================
def submit():
    nif_code = entry_nif.get()
    supplier_name = entry_name.get()

    if nif_code and supplier_name:
        add_supplier(nif_code, supplier_name)
        # Clear the entries after insertion
        entry_nif.delete(0, tk.END)
        entry_name.delete(0, tk.END)
    else:
        messagebox.showwarning("Input Error", "Please fill all fields.")

# ==========================================================
# Main GUI
# ==========================================================
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Add Supplier")

    tk.Label(root, text="Supplier NIF Code:").grid(row=0, column=0, padx=10, pady=5, sticky="e")
    entry_nif = tk.Entry(root, width=30)
    entry_nif.grid(row=0, column=1, padx=10, pady=5)

    tk.Label(root, text="Supplier Name:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
    entry_name = tk.Entry(root, width=30)
    entry_name.grid(row=1, column=1, padx=10, pady=5)

    submit_button = tk.Button(root, text="Add Supplier", command=submit)
    submit_button.grid(row=2, column=0, columnspan=2, pady=10)

    root.mainloop()
