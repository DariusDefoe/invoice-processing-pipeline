#!/usr/bin/env python3
"""
VAT Report Generator
- Output exclusive: PDF OR CSV (radio toggle).
- Always generates Chancery first, then Residence (single output).
- CSV: each line ends with a semicolon. If Numero_Factura > 20 chars, it truncated
  from the end (keep first 20). A truncation log CSV is produced alongside the output.

Env:
  MYSQL_CONNECTION=mysql://user:pass@host:port/dbname
Output dir:
  ~/Desktop/exports
"""

import os
from datetime import datetime
from contextlib import contextmanager
from mysql.connector import Error
from db import get_cnx  # central DB connector
from tkinter import (
    Tk,
    Label,
    Button,
    OptionMenu,
    StringVar,
    messagebox,
    Radiobutton,
    IntVar,
)

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.pdfgen import canvas

# ==========================================================
# Context manager for automatic cleanup
# ==========================================================
@contextmanager
def db_cursor(commit=False):
    cnx = get_cnx()
    cur = cnx.cursor(dictionary=True)
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
# Config
# ==========================================================
OUTPUT_DIR = "~/Desktop/exports"
MAX_INVOICE_NUMBER_LEN = 12  # AEAT constraint
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================================
# Custom Canvas Class
# ==========================================================
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def _draw_footer(self, page_count):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.setFont("Helvetica", 6)
        self.drawString(15 * mm, A4[1] - 10 * mm, f"Generated on: {timestamp}")
        self.setFont("Helvetica", 8)
        self.drawCentredString(A4[0] / 2.0, 15 * mm, f"{self._pageNumber}/{page_count}")

# ==========================================================
# Data Fetching
# ==========================================================
COLUMNS = [
    "NIF",
    "Proveedor",  # may be empty if not present in the view
    "Numero_Factura",
    "Fecha_Devengo",
    "Importe_Total_Impuestos_Incluidos",
    "Cuotas_IVA",
]

SELECT_WITH_PROVEEDOR = ", ".join(
    [
        "NIF",
        "Proveedor AS Proveedor",
        "Numero_Factura",
        "Fecha_Devengo",
        "Importe_Total_Impuestos_Incluidos",
        "Cuotas_IVA",
    ]
)

SELECT_FALLBACK = ", ".join(
    [
        "NIF",
        "'' AS Proveedor",
        "Numero_Factura",
        "Fecha_Devengo",
        "Importe_Total_Impuestos_Incluidos",
        "Cuotas_IVA",
    ]
)

def fetch_data(view_name, quarter, fiscal_year):
    try:
        with db_cursor(commit=False) as cur:
            try:
                query = f"""
                SELECT {SELECT_WITH_PROVEEDOR}
                FROM {view_name}
                WHERE Trimestre = %s AND Fiscal_Year = %s
                ORDER BY NIF, Fecha_Devengo, Numero_Factura
                """
                cur.execute(query, (quarter, fiscal_year))
            except Error:
                query = f"""
                SELECT {SELECT_FALLBACK}
                FROM {view_name}
                WHERE Trimestre = %s AND Fiscal_Year = %s
                ORDER BY NIF, Fecha_Devengo, Numero_Factura
                """
                cur.execute(query, (quarter, fiscal_year))

            rows = cur.fetchall() or []
            norm = [{k: r.get(k, "") for k in COLUMNS} for r in rows]
            return norm

    except Error as err:
        messagebox.showerror("Database Error", f"Error: {err}")
        return []


# ==========================================================
# Helpers
# ==========================================================
def _fmt_amount(x):
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return str(x)


def _fmt_date(d):
    # Accepts date/datetime/str; returns yyyy-mm-dd string
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    try:
        s = str(d)
        return s[:10]
    except Exception:
        return str(d)


def _fmt_date_ddmmyyyy(d):
    """Return date as dd-mm-YYYY (preferred for AEAT CSV)."""
    if hasattr(d, "strftime"):
        return d.strftime("%d-%m-%Y")
    s = str(d)
    s10 = s[:10]
    try:
        # Convert common YYYY-MM-DD to DD-MM-YYYY
        if "-" in s10 and len(s10) == 10:
            parts = s10.split("-")
            if len(parts) == 3 and len(parts[0]) == 4:
                y, m, d2 = parts
                return f"{d2}-{m}-{y}"
        # If already dd/mm/yyyy or dd-mm-yyyy, normalize to dashes
        if "/" in s10 and len(s10) == 10:
            return s10.replace("/", "-")
        return s10
    except Exception:
        return s10


# ==========================================================
# PDF Generation (Chancery first, then Residence)
# ==========================================================
def generate_pdf(chancery_rows, residence_rows, output_file, fiscal_year, quarter):
    if not chancery_rows and not residence_rows:
        messagebox.showinfo("No Data", "No data for the selected period.")
        return

    doc = BaseDocTemplate(
        output_file,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    total_style = ParagraphStyle(
        name="Total",
        parent=styles["Normal"],
        fontSize=10,
        alignment=TA_RIGHT,
        spaceBefore=6,
        spaceAfter=12,
    )
    h_style = styles["Heading2"]
    h_style.spaceBefore = 6
    h_style.spaceAfter = 6

    frame = Frame(
        doc.leftMargin, doc.bottomMargin, doc.width, doc.height - 10 * mm, id="normal"
    )

    def header(canvas_obj, _):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica-Bold", 12)
        title = f"Relación de Facturas - Modelo 362 — Q{quarter} / {fiscal_year}"
        canvas_obj.drawString(doc.leftMargin, A4[1] - 15 * mm, title)
        canvas_obj.restoreState()

    doc.addPageTemplates([PageTemplate(id="Report", frames=frame, onPage=header)])

    elements = []

    def rows_to_table(rows, start_serial=1):
        table_header = [
            Paragraph("Serial Nº", styles["Heading4"]),
            Paragraph("NIF", styles["Heading4"]),
            Paragraph("Proveedor", styles["Heading4"]),
            Paragraph("Nº Factura", styles["Heading4"]),
            Paragraph("Fecha Devengo", styles["Heading4"]),
            Paragraph("Importe Total (€)", styles["Heading4"]),
            Paragraph("Cuota IVA (€)", styles["Heading4"]),
        ]
        col_widths = [15 * mm, 30 * mm, 50 * mm, 35 * mm, 25 * mm, 25 * mm, 25 * mm]

        data = [table_header]
        serial = start_serial
        subtotal_vat = 0.0

        for r in rows:
            nif = r.get("NIF", "")
            prov = r.get("Proveedor", "")
            nf = r.get("Numero_Factura", "")
            fecha = _fmt_date(r.get("Fecha_Devengo", ""))
            importe = r.get("Importe_Total_Impuestos_Incluidos", 0) or 0
            cuota = r.get("Cuotas_IVA", 0) or 0
            try:
                subtotal_vat += float(cuota)
            except Exception:
                pass

            data.append(
                [
                    Paragraph(str(serial), styles["Normal"]),
                    Paragraph(str(nif), styles["Normal"]),
                    Paragraph(str(prov), styles["Normal"]),
                    Paragraph(str(nf), styles["Normal"]),
                    Paragraph(str(fecha), styles["Normal"]),
                    Paragraph(_fmt_amount(importe), styles["Normal"]),
                    Paragraph(_fmt_amount(cuota), styles["Normal"]),
                ]
            )
            serial += 1

        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("ALIGN", (2, 1), (2, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.whitesmoke],
                    ),
                ]
            )
        )
        return table, serial, subtotal_vat

    serial = 1
    grand_total_vat = 0.0

    if chancery_rows:
        elements.append(Paragraph("Chancery", h_style))
        tbl, serial, sub_vat = rows_to_table(chancery_rows, start_serial=serial)
        elements.append(tbl)
        elements.append(
            Paragraph(
                f"<b>Total Cuotas IVA (Chancery): € {sub_vat:,.2f}</b>", total_style
            )
        )
        elements.append(Spacer(1, 6))
        grand_total_vat += sub_vat

    if residence_rows:
        elements.append(Paragraph("Residence", h_style))
        tbl, serial, sub_vat = rows_to_table(residence_rows, start_serial=serial)
        elements.append(tbl)
        elements.append(
            Paragraph(
                f"<b>Total Cuotas IVA (Residence): € {sub_vat:,.2f}</b>", total_style
            )
        )
        elements.append(Spacer(1, 6))
        grand_total_vat += sub_vat

    elements.append(Spacer(1, 12))
    elements.append(
        Paragraph(
            f"<b>Gran Total Cuotas IVA: € {grand_total_vat:,.2f}</b>", total_style
        )
    )

    try:
        doc.build(elements, canvasmaker=NumberedCanvas)
        messagebox.showinfo("Success", f"PDF report generated: {output_file}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate PDF: {e}")


# ==========================================================
# CSV Generation (Chancery then Residence)
# Required order per line:
#   NIF; Importe_Total_Impuestos_Incluidos; Numero_Factura(<=20); Cuotas_IVA; Fecha_Devengo(dd-mm-aaaa);
# ==========================================================
def generate_csv(chancery_rows, residence_rows, output_file):
    """
    Write CSV with trailing semicolon per line; return list of truncations.

    Returns: list of dicts with keys:
      section, NIF, Proveedor, Numero_Factura_Original, Numero_Factura_Truncada,
      Fecha_Devengo, Importe, Cuota
    """
    if not chancery_rows and not residence_rows:
        messagebox.showinfo("No Data", "No data for the selected period.")
        return []

    truncations = []

    try:
        with open(output_file, mode="w", newline="", encoding="utf-8") as f:
            for section_name, rows in (
                ("Chancery", chancery_rows),
                ("Residence", residence_rows),
            ):
                for r in rows:
                    nif = str(r.get("NIF", ""))
                    nf = str(r.get("Numero_Factura", ""))
                    importe = str(r.get("Importe_Total_Impuestos_Incluidos", ""))
                    cuota = str(r.get("Cuotas_IVA", ""))
                    fecha = _fmt_date_ddmmyyyy(r.get("Fecha_Devengo", ""))

                    original_nf = nf
                    if len(nf) > MAX_INVOICE_NUMBER_LEN:
                        nf = nf[:MAX_INVOICE_NUMBER_LEN]
                        truncations.append(
                            {
                                "section": section_name,
                                "NIF": nif,
                                "Proveedor": str(r.get("Proveedor", "")),
                                "Numero_Factura_Original": original_nf,
                                "Numero_Factura_Truncada": nf,
                                "Fecha_Devengo": fecha,
                                "Importe": importe,
                                "Cuota": cuota,
                            }
                        )

                    # Order: NIF; Importe; Numero; Cuota; Fecha;  (trailing semicolon)
                    vals = [nif, importe, nf, cuota, fecha]
                    f.write(";".join(vals) + ";\n")

        return truncations
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save CSV: {e}")
        return []


# ==========================================================
# Main GUI
# ==========================================================
def main():
    def generate_report():
        selected_quarter = quarter_var.get()
        selected_year = year_var.get()

        if not selected_quarter or not selected_year:
            messagebox.showwarning(
                "Input Required", "Please select both quarter and fiscal year."
            )
            return

        # Fetch BOTH datasets: Chancery first, then Residence
        chancery_view = "Invoices_Chancery_Vat"
        residence_view = "Invoices_Residence_Vat"

        chancery_rows = fetch_data(chancery_view, selected_quarter, selected_year)
        residence_rows = fetch_data(residence_view, selected_quarter, selected_year)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"VAT_Q{selected_quarter}_{selected_year}_{timestamp}"

        if output_type.get() == 1:  # PDF
            pdf_file = os.path.join(OUTPUT_DIR, base_filename + ".pdf")
            generate_pdf(
                chancery_rows, residence_rows, pdf_file, selected_year, selected_quarter
            )
        else:  # CSV
            csv_file = os.path.join(OUTPUT_DIR, base_filename + ".csv")
            truncs = generate_csv(chancery_rows, residence_rows, csv_file)

            # If any truncations occurred, persist a log next to the CSV
            if truncs:
                log_file = os.path.join(
                    OUTPUT_DIR, base_filename + "_truncated_log.csv"
                )
                try:
                    with open(log_file, "w", encoding="utf-8", newline="") as lf:
                        # header
                        lf.write(
                            "section;NIF;Proveedor;Numero_Factura_Original;Numero_Factura_Truncada;Fecha_Devengo;Importe;Cuota;\n"
                        )
                        for t in truncs:
                            lf.write(
                                ";".join(
                                    [
                                        str(t["section"]),
                                        str(t["NIF"]),
                                        str(t["Proveedor"]),
                                        str(t["Numero_Factura_Original"]),
                                        str(t["Numero_Factura_Truncada"]),
                                        str(t["Fecha_Devengo"]),
                                        str(t["Importe"]),
                                        str(t["Cuota"]),
                                    ]
                                )
                                + ";\n"
                            )
                    messagebox.showinfo(
                        "CSV saved with truncations",
                        f"CSV saved to:\n{csv_file}\n\nTruncated invoices logged to:\n{log_file}\n\nTotal truncated: {len(truncs)}",
                    )
                except Exception as e:
                    messagebox.showwarning(
                        "CSV saved (log failed)",
                        f"CSV saved to:\n{csv_file}\n\nFailed to write truncation log: {e}",
                    )
            else:
                messagebox.showinfo(
                    "Success",
                    f"CSV file saved: {csv_file}\nNo invoice numbers required truncation.",
                )

    root = Tk()
    root.title("Generate VAT Report (Chancery → Residence)")

    # Quarter selector (default to current quarter)
    quarter_var = StringVar()
    Label(root, text="Select Quarter:").pack(pady=5)
    quarters = ["1", "2", "3", "4"]
    month = datetime.now().month
    current_quarter = str((month - 1) // 3 + 1)
    quarter_var.set(current_quarter)
    OptionMenu(root, quarter_var, *quarters).pack()

    # Year selector (default to current year)
    year_var = StringVar()
    Label(root, text="Select Fiscal Year:").pack(pady=5)
    current_year = datetime.now().year
    years = [str(y) for y in range(current_year - 5, current_year + 1)]
    year_var.set(str(current_year))
    OptionMenu(root, year_var, *years).pack()

    # Output type (EXCLUSIVE: PDF or CSV)
    output_type = IntVar(value=1)
    Label(root, text="Select Output Format:").pack(pady=5)
    Radiobutton(root, text="PDF", variable=output_type, value=1).pack()
    Radiobutton(
        root, text="LibreOffice Calc (CSV)", variable=output_type, value=2
    ).pack()

    Button(root, text="Generate Report", command=generate_report).pack(pady=20)

    root.mainloop()


if __name__ == "__main__":
    main()
