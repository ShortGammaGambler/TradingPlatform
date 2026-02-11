import os
import csv
from fpdf import FPDF

# ---------- CONFIG ----------
input_folder = r"C:\Users\Trav'sTraderLounge\Desktop\TOS_Scripts_Backup"
output_csv = r"C:\Users\Trav'sTraderLounge\Desktop\TOS_Scripts_Output.csv"
output_pdf = r"C:\Users\Trav'sTraderLounge\Desktop\TOS_Scripts_Output.pdf"
font_path = r"C:\Users\Trav'sTraderLounge\Desktop\DejaVuSans.ttf"  # Adjust if needed

# ---------- HELPERS ----------
def guess_type(filename):
    fname = filename.lower()
    if "index" in fname:
        return "Index"
    elif "etf" in fname:
        return "ETF"
    elif "equity" in fname:
        return "Equity"
    elif "dashboard" in fname:
        return "Dashboard"
    else:
        return "Unknown"

def guess_signal(filename):
    fname = filename.lower()
    if "index" in fname:
        return "+1=Sell, -1=Buy"
    elif "etf" in fname or "equity" in fname:
        return "+1=Buy, -1=Sell"
    elif "dashboard" in fname:
        return "0-5 Star Score"
    else:
        return "N/A"

# ---------- READ SCRIPTS ----------
script_data = []

# Create input folder if it doesn't exist
if not os.path.exists(input_folder):
    os.makedirs(input_folder)
    print(f"[!] Input folder created at {input_folder}. Please put your .ts scripts there and rerun.")
    exit()

for file in os.listdir(input_folder):
    if file.endswith(".ts"):
        path = os.path.join(input_folder, file)
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        script_data.append({
            "name": file.replace(".ts",""),
            "type": guess_type(file),
            "signal": guess_signal(file),
            "code": code
        })

# ---------- CREATE CSV ----------
with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Script Name","Type","Signal Interpretation","Code"])
    for s in script_data:
        writer.writerow([s["name"], s["type"], s["signal"], s["code"]])

print(f"[+] CSV created: {output_csv}")

# ---------- CREATE PDF ----------
pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_font('DejaVu', '', font_path, uni=True)
pdf.set_font("DejaVu", "", 12)

# Cheat sheet page
pdf.add_page()
pdf.set_font("DejaVu", "B", 16)
pdf.cell(0, 10, "TOS Script Cheat Sheet", ln=True, align="C")
pdf.ln(5)
pdf.set_font("DejaVu", "", 12)
pdf.multi_cell(0, 6, "Signal Reference:\n+1 = Buy / Sell depending on script\n-1 = Opposite trade\n0-5 = Dashboard star rating\n")
pdf.ln(2)
pdf.set_font("DejaVu", "B", 12)
pdf.cell(60, 6, "Script Name", 1)
pdf.cell(40, 6, "Type", 1)
pdf.cell(40, 6, "Signal", 1)
pdf.ln()

for s in script_data:
    pdf.set_font("DejaVu", "", 12)
    if "+1" in s["signal"]:
        pdf.set_text_color(0,128,0)
    elif "-1" in s["signal"]:
        pdf.set_text_color(255,0,0)
    else:
        pdf.set_text_color(0,0,0)
    pdf.cell(60,6,s["name"],1)
    pdf.cell(40,6,s["type"],1)
    pdf.cell(40,6,s["signal"],1)
    pdf.ln()
    pdf.multi_cell(0,5,s["code"])
    pdf.set_text_color(0,0,0)

pdf.output(output_pdf)
print(f"[+] PDF created: {output_pdf}")
