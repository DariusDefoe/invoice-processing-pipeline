#!/usr/bin/env python3
import os, csv
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from mysql.connector import Error
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
# Queries
# ==========================================================
BASE_QUERY = """
SELECT
  n.Supplier_Name          AS Proveedor,
  i.`Number`               AS Numero_Factura,
  i.Date                   AS Fecha_Devengo,
  i.Total                  AS Importe_Total_Impuestos_Incluidos,
  i.Vat                    AS Cuotas_IVA,
  v.Voucher_Number,
  ha.Name                  AS Head_of_Accounts
FROM {table} i
LEFT JOIN NIF_Codes       n  ON i.Supplier_ID = n.Supplier_ID
LEFT JOIN Vouchers        v  ON i.Voucher_ID = v.Voucher_ID
LEFT JOIN Head_of_Accounts ha ON v.Head_of_Accounts_ID = ha.Head_of_Accounts_ID
WHERE i.Quarter = %s AND i.Year = %s AND i.Refundable = 1
ORDER BY i.Date, i.Number
"""

def fetch(table, q, y):
    try:
        with db_cursor(commit=False) as cur:
            cur.execute(BASE_QUERY.format(table=table),(q,y))
            rows=cur.fetchall(); cur.close(); return rows
    except Error as e:
        messagebox.showerror("Error", f"Error: {e}")
  
# ==========================================================
# PDF helpers
# ==========================================================

styles=getSampleStyleSheet()
total_style=ParagraphStyle(name='Total', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT, spaceAfter=8)

HEADERS = [
    "Proveedor","Nº Factura","Fecha Devengo","Importe Total (€)","Cuota IVA (€)","Voucher Nº","Head of Accounts"
]
COLS = [50*mm,35*mm,25*mm,28*mm,25*mm,25*mm,35*mm]

def table_for(data):
    tdata=[[Paragraph(h, styles['Heading4']) for h in HEADERS]]
    for r in data:
        tdata.append([
            Paragraph(str(r[0] or ""), styles['Normal']),
            Paragraph(str(r[1] or ""), styles['Normal']),
            Paragraph(str(r[2] or ""), styles['Normal']),
            Paragraph(f"{(r[3] or 0):,.2f}", styles['Normal']),
            Paragraph(f"{(r[4] or 0):,.2f}", styles['Normal']),
            Paragraph("" if r[5] is None else str(r[5]), styles['Normal']),
            Paragraph(str(r[6] or ""), styles['Normal']),
        ])
    t=Table(tdata, colWidths=COLS, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.lightblue),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('GRID',(0,0),(-1,-1),0.25,colors.grey),
        ('FONTSIZE',(0,0),(-1,-1),8),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.whitesmoke]),
    ]))
    return t

def build_pdf(ch_data, rs_data, out_file, year, quarter):
    if not ch_data and not rs_data:
        messagebox.showinfo("No Data","No data for the selected period."); return
    doc=BaseDocTemplate(out_file, pagesize=landscape(A4),
                        rightMargin=15*mm,leftMargin=15*mm,topMargin=15*mm,bottomMargin=15*mm)
    frame=Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height-20*mm)
    def header(c,_):
        c.saveState(); c.setFont('Helvetica-Bold',12)
        c.drawString(doc.leftMargin, landscape(A4)[1]-20*mm, f"Modelo 362 – Q{quarter} {year}")
        c.restoreState()
    doc.addPageTemplates([PageTemplate(id='p', frames=frame, onPage=header)])

    elems=[]
    if ch_data:
        elems.append(Paragraph("Relación de Facturas – Chancery", styles['Title']))
        elems.append(Spacer(1,6))
        elems.append(table_for(ch_data))
        ch_total=sum((r[4] or 0) for r in ch_data)
        elems.append(Spacer(1,6))
        elems.append(Paragraph(f"<b>Total Cuotas IVA (Chancery): € {ch_total:,.2f}</b>", total_style))
    if rs_data:
        if ch_data: elems.append(PageBreak())
        elems.append(Paragraph("Relación de Facturas – Residence", styles['Title']))
        elems.append(Spacer(1,6))
        elems.append(table_for(rs_data))
        rs_total=sum((r[4] or 0) for r in rs_data)
        elems.append(Spacer(1,6))
        elems.append(Paragraph(f"<b>Total Cuotas IVA (Residence): € {rs_total:,.2f}</b>", total_style))

    doc.build(elems, canvasmaker=NumberedCanvas)
    messagebox.showinfo("Success", f"PDF generated:\n{out_file}")

# ==========================================================
# CSV
# ==========================================================
def write_csv(rows, path):
    headers=["Proveedor","Numero_Factura","Fecha_Devengo",
             "Importe_Total_Impuestos_Incluidos","Cuotas_IVA","Voucher_Number","Head_of_Accounts"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w=csv.writer(f, delimiter=";"); w.writerow(headers)
        for r in rows:
            rr=list(r); rr[5] = "" if rr[5] is None else rr[5]; w.writerow(rr)

# ==========================================================
# GUI
# ==========================================================
def main():
    root=Tk(); root.title("Generate VAT Report (Chancery + Residence)")
    quarter=StringVar(); year=StringVar(); out=IntVar(value=1)

    Label(root, text="Quarter").pack(pady=4)
    OptionMenu(root, quarter, '1','2','3','4').pack()
    Label(root, text="Year").pack(pady=4)
    y=datetime.now().year
    OptionMenu(root, year, *[str(i) for i in range(y-5, y+1)]).pack()
    Label(root, text="Output").pack(pady=4)
    Radiobutton(root, text="PDF (single file, both sections)", variable=out, value=1).pack()
    Radiobutton(root, text="CSV (two files: Chancery & Residence)", variable=out, value=2).pack()

    def run():
        q, yv = quarter.get(), year.get()
        if not q or not yv:
            messagebox.showwarning("Input Required","Select quarter and year"); return
        ch = fetch("Invoices_Chancery", q, yv)
        rs = fetch("Invoices_Residence", q, yv)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"VatVouchers_Q{q}_{yv}_{ts}"
        if out.get()==1:
            pdf = OUT_DIR / f"{base}.pdf"
            build_pdf(ch, rs, str(pdf), yv, q)
        else:
            cpath = OUT_DIR / f"{base}_Chancery.csv"
            rpath = OUT_DIR / f"{base}_Residence.csv"
            if ch: write_csv(ch, cpath)
            if rs: write_csv(rs, rpath)
            messagebox.showinfo("Success", f"CSV saved:\n{cpath if ch else '(no chancery data)'}\n{rpath if rs else '(no residence data)'}")

    Button(root, text="Generate", command=run).pack(pady=14)
    root.mainloop()

if __name__=="__main__":
    main()