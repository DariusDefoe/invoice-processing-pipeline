#!/usr/bin/env python3
import tkinter as tk
from tkinter import messagebox
from contextlib import contextmanager
from mysql.connector import Error
# Ensure db.py exists, or replace this import with the connection function
from db import get_cnx 

# ==========================================================
# Context manager (Fixed for UnboundLocalError)
# ==========================================================
@contextmanager
def db_cursor(commit=False):
    cnx = get_cnx()
    cur = None
    try:
        cur = cnx.cursor()
        yield cur
        if commit:
            cnx.commit()
    except Exception as e:
        cnx.rollback()
        raise e
    finally:
        if cur:
            cur.close()
        # Be careful closing cnx here if get_cnx() returns a pooled connection.
        # If it's a fresh connection every time, this is fine.
        cnx.close()

# ==========================================================
# Function to add supplier
# ==========================================================
def add_supplier(nif_code, supplier_name):
    success = False
    new_id = 0
    
    try:
        with db_cursor(commit=True) as cur:
            insert_query = """
            INSERT INTO administration.NIF_Codes (Supplier_NIF_Code, Supplier_Name)
            VALUES (%s, %s)
            """
            cur.execute(insert_query, (nif_code, supplier_name))
            
            # Use lastrowid only if you have an AUTO_INCREMENT column. 
            # If NIF is the key, this might return 0.
            new_id = cur.lastrowid 
            success = True
            
    except Error as e:
        messagebox.showerror("Database Error", f"Error: {e}")
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    # Show success message OUTSIDE the database transaction
    if success:
        id_display = new_id if new_id != 0 else nif_code
        messagebox.showinfo("Success", f"Supplier added successfully.\nID/NIF: {id_display}")

# ==========================================================
# Function to handle button click event
# ==========================================================
def submit():
    nif_code = entry_nif.get().strip() # Added strip() to remove accidental spaces
    supplier_name = entry_name.get().strip()

    if nif_code and supplier_name:
        add_supplier(nif_code, supplier_name)
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