#!/usr/bin/env python3

import os
import csv
from contextlib import contextmanager
from mysql.connector import Error
from db import get_cnx  # central DB connector
from tkinter import Tk, Label, Button, Entry, StringVar, LEFT, RIGHT, E, W, N, S, END
from tkinter import messagebox, filedialog
import time
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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
# Define output directory
# ==========================================================
DEFAULT_OUTPUT_DIR = "~Desktop/exports"

# Global variable for output directory (user can browse)
OUTPUT_DIR = DEFAULT_OUTPUT_DIR

# ==========================================================
# Define functions
# ==========================================================

def fetch_data(Colleague_ID, quarter, fiscal_year):
    try:
        with db_cursor(commit=False) as cur:
            cur.callproc('GetRelFactColleague', [Colleague_ID, quarter, fiscal_year])
            data = []
            for result in cur.stored_results():
                data = result.fetchall()
            return data
    except Error as e:
        messagebox.showerror("Error", f"Error: {e}")

def generate_csv(data, output_file):
    """
    Generate CSV summary per Agencia Tributaria guidelines:
    Nif Proveedor; Importe total (impuestos incluidos); Nº factura; Cuota IVA; Fecha devengo
    """
    if not data:
        return

    valid_data = [row for row in data if len(row) >= 13]
    if not valid_data:
        return

    try:
        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile, delimiter=";")
            for row in valid_data:
                nif = str(row[3])
                total = f"{float(row[6]):.2f}".rstrip("0").rstrip(".")
                invoice_no = str(row[5])
                iva = f"{float(row[8]):.2f}".rstrip("0").rstrip(".")
                try:
                    fecha_obj = datetime.strptime(str(row[7]), "%Y-%m-%d")
                    fecha = fecha_obj.strftime("%d-%m-%Y")
                except Exception:
                    fecha = str(row[7])
                writer.writerow([nif, total, invoice_no, iva, fecha])
        messagebox.showinfo("CSV Generated", f"CSV summary generated: {output_file}")
    except Exception as e:
        messagebox.showerror("CSV Generation Error", f"Error generating CSV: {e}")

def generate_pdf(data, output_file):
    if not data:
        messagebox.showinfo("No Data", "No data available to generate the report.")
        return

    valid_data = [row for row in data if len(row) >= 13]
    if not valid_data:
        messagebox.showinfo("No Valid Data", "No valid data rows found. Skipping PDF generation.")
        return

    doc = SimpleDocTemplate(output_file, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='QuarterHeader', parent=styles['Heading2'], alignment=1, spaceAfter=10))
    styles.add(ParagraphStyle(name='TableHeader', parent=styles['Normal'], fontSize=9, leading=12, alignment=1, textColor=colors.white))
    styles.add(ParagraphStyle(name='TableCell', parent=styles['Normal'], fontSize=8, leading=10))

    quarters = sorted(set((row[11], row[12]) for row in valid_data))

    for quarter, fiscal_year in quarters:
        quarter_data = [row for row in valid_data if row[11] == quarter and row[12] == fiscal_year]
        if not quarter_data:
            continue
        if elements:
            elements.append(PageBreak())
        colleague_name = quarter_data[0][0]
        nie = quarter_data[0][1]
        service_office = quarter_data[0][2]

        elements.append(Paragraph("Relación de Facturas - Modelo 362", styles['Title']))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(f"<b>Solicitante:</b> {colleague_name}", styles['Normal']))
        elements.append(Paragraph(f"<b>N.I.F. del solicitante:</b> {nie}", styles['Normal']))
        elements.append(Paragraph(f"<b>Ejercicio:</b> {fiscal_year}", styles['Normal']))
        elements.append(Paragraph(f"<b>Servicio u Oficina:</b> {service_office}", styles['Normal']))
        elements.append(Paragraph(f"<b>Trimestre:</b> {quarter}", styles['Normal']))
        elements.append(Spacer(1, 12))

        headers = ["NIF", "Proveedor", "Nº Factura", "Importe Total (€)", "Fecha Devengo", "Cuota IVA (€)"]
        data_table = [headers]
        vat_total = 0

        for row in quarter_data:
            supplier_name = Paragraph(str(row[4]), styles['TableCell'])
            data_row = [
                str(row[3]),
                supplier_name,
                str(row[5]),
                f"{float(row[6]):,.2f}",
                str(row[7]),
                f"{float(row[8]):,.2f}"
            ]
            data_table.append(data_row)
            vat_total += row[8]

        table = Table(data_table, colWidths=[30*mm, 50*mm, 30*mm, 30*mm, 30*mm, 30*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(f"<b>Total Cuotas IVA para Trimestre {quarter}: € {vat_total:,.2f}</b>", styles['Normal']))

    try:
        doc.build(elements)
        messagebox.showinfo("Report Generated", f"PDF report generated: {output_file}")
    except Exception as e:
        messagebox.showerror("PDF Generation Error", f"An error occurred: {e}")

def generate_report(Colleague_ID, quarter, fiscal_year):
    data = fetch_data(Colleague_ID, quarter, fiscal_year)
    if not data:
        messagebox.showwarning("No Data", "No data found for the provided criteria.")
        return

    colleague_full_name = data[0][0]
    name_parts = colleague_full_name.strip().split()
    name = name_parts[0]
    surname = "_".join(name_parts[1:]) if len(name_parts) > 1 else ""

    name_sanitized = name.replace(" ", "_")
    surname_sanitized = surname.replace(" ", "_")

    quarter_str = f"Q{quarter}" if quarter else "AllQuarters"
    fiscal_year_str = str(fiscal_year) if fiscal_year else "AllYears"

    pdf_filename = f"RelFactColleague_report_{name_sanitized}_{surname_sanitized}_{quarter_str}_{fiscal_year_str}.pdf"
    csv_filename = f"RelFactColleague_summary_{name_sanitized}_{surname_sanitized}_{quarter_str}_{fiscal_year_str}.csv"

    output_pdf = os.path.join(OUTPUT_DIR, pdf_filename)
    output_csv = os.path.join(OUTPUT_DIR, csv_filename)

    generate_pdf(data, output_pdf)
    generate_csv(data, output_csv)

def select_and_generate_report():
    Colleague_ID_input = Colleague_ID_var.get().strip()
    quarter_input = quarter_var.get().strip()
    fiscal_year_input = fiscal_year_var.get().strip()

    try:
        Colleague_ID = int(Colleague_ID_input) if Colleague_ID_input else None
    except ValueError:
        messagebox.showerror("Invalid Input", "Colleague ID must be an integer.")
        return
    try:
        quarter = int(quarter_input) if quarter_input else None
    except ValueError:
        messagebox.showerror("Invalid Input", "Quarter must be 1–4.")
        return
    try:
        fiscal_year = int(fiscal_year_input) if fiscal_year_input else None
    except ValueError:
        messagebox.showerror("Invalid Input", "Fiscal Year must be valid.")
        return
    if quarter is not None and not (1 <= quarter <= 4):
        messagebox.showerror("Invalid Input", "Quarter must be between 1 and 4.")
        return
    if fiscal_year is not None and not (1900 <= fiscal_year <= 2100):
        messagebox.showerror("Invalid Input", "Fiscal Year must be 1900–2100.")
        return

    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
        except OSError as e:
            messagebox.showerror("Directory Error", f"Could not create output directory: {e}")
            return
    generate_report(Colleague_ID, quarter, fiscal_year)

def browse_directory():
    global OUTPUT_DIR
    directory = filedialog.askdirectory(initialdir=DEFAULT_OUTPUT_DIR, title="Select Output Directory")
    if directory:
        OUTPUT_DIR = directory
        output_dir_var.set(OUTPUT_DIR)

def main():
    root = Tk()
    root.title("Generate RelFactColleague Report")

    root.columnconfigure(1, weight=1)

    Label(root, text="Colleague ID (INT):").grid(row=0, column=0, padx=10, pady=5, sticky=E)
    global Colleague_ID_var
    Colleague_ID_var = StringVar()
    Entry(root, textvariable=Colleague_ID_var).grid(row=0, column=1, padx=10, pady=5, sticky=W+E)

    Label(root, text="Quarter (1-4):").grid(row=1, column=0, padx=10, pady=5, sticky=E)
    global quarter_var
    quarter_var = StringVar()
    Entry(root, textvariable=quarter_var).grid(row=1, column=1, padx=10, pady=5, sticky=W+E)

    Label(root, text="Fiscal Year (e.g., 2023):").grid(row=2, column=0, padx=10, pady=5, sticky=E)
    global fiscal_year_var
    fiscal_year_var = StringVar()
    Entry(root, textvariable=fiscal_year_var).grid(row=2, column=1, padx=10, pady=5, sticky=W+E)

    # Output directory selection
    Label(root, text="Output Directory:").grid(row=3, column=0, padx=10, pady=5, sticky=E)
    global output_dir_var
    output_dir_var = StringVar(value=OUTPUT_DIR)
    Entry(root, textvariable=output_dir_var, state="readonly").grid(row=3, column=1, padx=10, pady=5, sticky=W+E)
    Button(root, text="Browse", command=browse_directory).grid(row=3, column=2, padx=5, pady=5)

    generate_button = Button(root, text="Generate Report", command=select_and_generate_report)
    generate_button.grid(row=4, column=0, columnspan=3, pady=15)

    root.mainloop()

if __name__ == "__main__":
    main()
