#!/usr/bin/env python3
import os, csv
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from mysql.connector import DBError
from db import get_cnx  # central DB connector
from tkinter import Tk, Label, Button, OptionMenu, StringVar, Radiobutton, IntVar, messagebox
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.pdfgen import canvas

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
# Canvas with Page Numbers
# ==========================================================

class NumberedCanvas(canvas.Canvas):
    def __init__(self,*a,**k):
        super().__init__(*a,**k); self._saved=[]
    def showPage(self):
        self._saved.append(dict(self.__dict__)); self._startPage()
    def save(self):
        n=len(self._saved)
        for st in self._saved:
            self.__dict__.update(st); self._draw(n); super().showPage()
        super().save()
    def _draw(self,n):
        ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        w,h=self._pagesize
        self.setFont("Helvetica",6); self.drawString(15*mm,h-10*mm,f"Generated on: {ts}")
        self.setFont("Helvetica",8); self.drawCentredString(w/2,15*mm,f"{self._pageNumber}/{n}")

# ==========================================================
# Output Directory setup
# ==========================================================

OUT_DIR = Path.home()/ "Desktop" / "exports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================================
# Fetch Chancery Data
# ==========================================================
def fetch_chancery_data(quarter, fiscal_year):
    try:
        with db_cursor() as cur:
            query = """ 
            SELECT
            n.Supplier_Name                          AS Proveedor,
            i.`Number`                               AS Numero_Factura,
            i.Date                                   AS Fecha_Devengo,
            i.Total                                  AS Importe_Total_Impuestos_Incluidos,
            i.Vat                                    AS Cuotas_IVA,
            GROUP_CONCAT(DISTINCT v.Voucher_Number ORDER BY v.Voucher_Number SEPARATOR ', ') AS Voucher_Numbers,
            MAX(ha.Head_of_Accounts_Name)            AS Head_of_Accounts
            FROM Invoices_Chancery i
            LEFT JOIN NIF_Codes n          ON n.Supplier_ID = i.Supplier_ID
            LEFT JOIN Vouchers_Chancery vc ON vc.Invoice_ID = i.ID
            LEFT JOIN Vouchers v           ON v.Voucher_ID = vc.Voucher_ID
            LEFT JOIN Head_of_Accounts ha  ON ha.Head_of_Accounts_ID = v.Head_of_Accounts_ID
            WHERE QUARTER(i.Date) = %s AND YEAR(i.Date) = %s AND i.Refundable = 1
            GROUP BY i.ID, n.Supplier_Name, i.`Number`, i.Date, i.Total, i.Vat
            ORDER BY n.Supplier_Name ASC, i.Date ASC, i.`Number` ASC;
            """
            cur.execute(query, (quarter, fiscal_year))
            return cur.fetchall()
    except DBError as e:
        messagebox.showerror("Database Error", f"Error fetching Chancery Data: {e}")
        return []

# ==========================================================
# Fetch Residence Data
# ==========================================================
def fetch_residence_data(quarter, fiscal_year):
    try:
        with db_cursor() as cur:
            query = """ 
            SELECT
            n.Supplier_Name                          AS Proveedor,
            i.`Number`                               AS Numero_Factura,
            i.Date                                   AS Fecha_Devengo,
            i.Total                                  AS Importe_Total_Impuestos_Incluidos,
            i.Vat                                    AS Cuotas_IVA,
            GROUP_CONCAT(DISTINCT v.Voucher_Number ORDER BY v.Voucher_Number SEPARATOR ', ') AS Voucher_Numbers,
            MAX(ha.Head_of_Accounts_Name)            AS Head_of_Accounts
            FROM Invoices_Residence i
            LEFT JOIN NIF_Codes n          ON n.Supplier_ID = i.Supplier_ID
            LEFT JOIN Vouchers_Chancery vc ON vc.Invoice_ID = i.ID
            LEFT JOIN Vouchers v           ON v.Voucher_ID = vc.Voucher_ID
            LEFT JOIN Head_of_Accounts ha  ON ha.Head_of_Accounts_ID = v.Head_of_Accounts_ID
            WHERE QUARTER(i.Date) = %s AND YEAR(i.Date) = %s AND i.Refundable = 1
            GROUP BY i.ID, n.Supplier_Name, i.`Number`, i.Date, i.Total, i.Vat
            ORDER BY n.Supplier_Name ASC, i.Date ASC, i.`Number` ASC;
            """
            cur.execute(query, (quarter, fiscal_year))
            return cur.fetchall()
    except DBError as e:
        messagebox.showerror("Database Error", f"Error fetching Residence Data: {e}")
        return []

# ==========================================================
# PDF Generation
# ==========================================================
def generate_pdf(chancery_data, residence_data, output_file, fiscal_year, quarter):
    if not chancery_data and not residence_data:
        messagebox.showinfo("No Data", "No data for the selected period.")
        return

    doc = BaseDocTemplate(
        output_file,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm
    )
    styles = getSampleStyleSheet()
    total_style = ParagraphStyle(name='Total', parent=styles['Normal'], fontSize=8, alignment=TA_RIGHT, spaceAfter=6)
    elements = []

    # Shared Table settings
    col_widths = [70 * mm, 40 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm, 40 * mm]
    t_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
    ])

    def create_table_section(data, title, label):
        elements.append(Paragraph(f"{title} (Modelo 362)", styles['Title']))
        elements.append(Spacer(1, 12))
        
        table_header = [
            Paragraph("Proveedor", styles['Heading4']),
            Paragraph("Nº Factura", styles['Heading4']),
            Paragraph("Fecha Devengo", styles['Heading4']),
            Paragraph("Importe Total (€)", styles['Heading4']),
            Paragraph("Cuota IVA (€)", styles['Heading4']),
            Paragraph("Voucher Nº", styles['Heading4']),
            Paragraph("Head of Accounts", styles['Heading4'])
        ]
        table_data = [table_header]
        total_vat = 0
        for row in data:
            table_data.append([
                Paragraph(str(row[0]), styles['Normal']),
                Paragraph(str(row[1]), styles['Normal']),
                Paragraph(str(row[2]), styles['Normal']),
                Paragraph(f"{row[3]:,.2f}", styles['Normal']),
                Paragraph(f"{row[4]:,.2f}", styles['Normal']),
                Paragraph("" if row[5] is None else str(row[5]), styles['Normal']),
                Paragraph(str(row[6]), styles['Normal'])
            ])
            total_vat += row[4]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(t_style)
        elements.append(table)
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"<b>Total Cuotas IVA ({label}): € {total_vat:,.2f}</b>", total_style))

    if chancery_data:
        create_table_section(chancery_data, "Chancery Data", "Chancery")
    
    if chancery_data and residence_data:
        elements.append(PageBreak())

    if residence_data:
        create_table_section(residence_data, "Residence Data", "Residence")

    def header_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica-Bold', 10)
        header_text = "Relación de Facturas de IVA"
        canvas_obj.drawString(doc_obj.leftMargin, landscape(A4)[1] - 15 * mm, header_text)
        canvas_obj.restoreState()

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 20 * mm)
    doc.addPageTemplates([PageTemplate(id='Report', frames=frame, onPage=header_footer)])

    try:
        doc.build(elements, canvasmaker=NumberedCanvas) 
        messagebox.showinfo("Success", f"PDF report generated: {output_file}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate PDF: {e}")

# ==========================================================
# CSV Generation
# ==========================================================
def generate_csv(chancery_data, residence_data, output_file):
    if not chancery_data and not residence_data:
        messagebox.showinfo("No Data", "No data for the selected period.")
        return
    headers = ["Proveedor", "Numero_Factura", "Fecha_Devengo", "Importe_Total_Impuestos_Incluidos", "Cuotas_IVA", "Voucher_Number", "Head_of_Accounts"]
    try:
        with open(output_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(headers)
            
            if chancery_data:
                writer.writerow(["--- CHANCERY DATA ---"])
                for row in chancery_data:
                    r = list(row)
                    r[5] = "" if r[5] is None else r[5]
                    writer.writerow(r)
            
            if residence_data:
                writer.writerow(["--- RESIDENCE DATA ---"])
                for row in residence_data:
                    r = list(row)
                    r[5] = "" if r[5] is None else r[5]
                    writer.writerow(r)
        messagebox.showinfo("Success", f"CSV file saved: {output_file}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save CSV: {e}")

# ==========================================================
# Main GUI
# ==========================================================
def main():
    def generate_report():
        selected_quarter = quarter_var.get()
        selected_year = year_var.get()
        if not selected_quarter or not selected_year:
            messagebox.showwarning("Input Required", "Please select both quarter and fiscal year.")
            return
        
        chancery_data = fetch_chancery_data(selected_quarter, selected_year)
        residence_data = fetch_residence_data(selected_quarter, selected_year)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"Vouchers_Q{selected_quarter}_{selected_year}_{timestamp}"
        
        if output_type.get() == 1:
            pdf_file = os.path.join(OUT_DIR, base_filename + ".pdf")
            generate_pdf(chancery_data, residence_data, pdf_file, selected_year, selected_quarter)
        else:
            csv_file = os.path.join(OUT_DIR, base_filename + ".csv")
            generate_csv(chancery_data, residence_data, csv_file)

    root = Tk()
    root.title("Generate Vat Vouchers Report")
    
    quarter_var = StringVar()
    Label(root, text="Select Quarter:").pack(pady=5)
    OptionMenu(root, quarter_var, '1', '2', '3', '4').pack()
    
    year_var = StringVar()
    Label(root, text="Select Fiscal Year:").pack(pady=5)
    current_year = datetime.now().year
    years = [str(y) for y in range(current_year - 5, current_year + 1)]
    OptionMenu(root, year_var, *years).pack()
    
    output_type = IntVar(value=1)
    Label(root, text="Select Output Format:").pack(pady=5)
    Radiobutton(root, text="PDF", variable=output_type, value=1).pack()
    Radiobutton(root, text="LibreOffice Calc (CSV)", variable=output_type, value=2).pack()
    
    Button(root, text="Generate Report", command=generate_report).pack(pady=20)
    root.mainloop()

if __name__ == "__main__":
    main()