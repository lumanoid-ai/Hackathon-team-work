"""12 nakli resumes banao — 3 strong, 5 mediocre, 4 weak. Din 1 pe karo, din 3 pe nahi.

Chalao:  python -m scripts.seed_resumes
"""
import os

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.core.llm import llm_json

OUT = "./data/resumes"

PROMPT = """Generate {n} fake resumes for a "{role}" role, quality level: {level}.
strong  = clearly exceeds the requirements
medium  = partially matches, some gaps
weak    = wrong domain or far too junior

Return ONLY a JSON array:
[{{"name":"","email":"","phone":"","summary":"",
   "experience":[{{"title":"","company":"","years":"","bullets":["",""]}}],
   "skills":[], "education":""}}]

Names should be varied and realistic. Emails must look real but use example.com.
Use plain ASCII only: no em dashes, no curly quotes, no accented letters, no emoji.
"""

# fpdf2 ke core fonts (Helvetica) sirf latin-1 samajhte hain.
# LLM aksar unicode bhej deta hai, isliye har string yahan se guzarni zaroori hai.
_REPLACE = {
    "\u2014": "-", "\u2013": "-", "\u2012": "-", "\u2212": "-",     # dashes
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u2032": "'",     # single quotes
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"',     # double quotes
    "\u2026": "...", "\u2022": "-", "\u00a0": " ", "\u200b": "",
    "\u20b9": "Rs.", "\u20ac": "EUR", "\u00b7": "-",
}


def clean(text) -> str:
    """Kisi bhi text ko PDF-safe latin-1 mein badal do."""
    text = "" if text is None else str(text)
    for bad, good in _REPLACE.items():
        text = text.replace(bad, good)
    # jo bacha khucha unicode reh gaya (accented naam waghera) — drop kar do
    return text.encode("latin-1", errors="ignore").decode("latin-1")


class Resume(FPDF):
    """Har method ke baad cursor left margin pe wapis aata hai.
    (multi_cell default cursor ko RIGHT margin pe chhorta hai — agli call crash ho jati hai.)"""

    def row(self, txt: str, h: int = 6):
        self.cell(0, h, clean(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def para(self, txt: str, h: int = 5):
        self.multi_cell(0, h, clean(txt), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def heading(self, txt: str):
        self.set_font("Helvetica", "B", 12)
        self.row(txt, 8)
        self.set_font("Helvetica", "", 10)


def to_pdf(r: dict, path: str):
    pdf = Resume()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.row(r.get("name", "Unknown"), 10)

    pdf.set_font("Helvetica", "", 10)
    pdf.row(f"{r.get('email','')} | {r.get('phone','')}")
    pdf.ln(2)
    pdf.para(r.get("summary", ""))
    pdf.ln(2)

    pdf.heading("Experience")
    for e in r.get("experience", []):
        pdf.set_font("Helvetica", "B", 10)
        pdf.row(f"{e.get('title','')} - {e.get('company','')} ({e.get('years','')})")
        pdf.set_font("Helvetica", "", 10)
        for b in e.get("bullets", []):
            pdf.para(f"  - {b}")
    pdf.ln(2)

    pdf.heading("Skills")
    pdf.para(", ".join(r.get("skills", [])))
    pdf.ln(1)
    pdf.para(f"Education: {r.get('education','')}")

    pdf.output(path)


def safe_filename(name: str) -> str:
    keep = [c if c.isalnum() else "_" for c in clean(name)]
    return "".join(keep).strip("_") or "candidate"


def main(role: str = "Backend Engineer"):
    os.makedirs(OUT, exist_ok=True)
    i = 0
    for level, n in [("strong", 3), ("medium", 5), ("weak", 4)]:
        people = llm_json(PROMPT.format(n=n, role=role, level=level))
        for p in people:
            i += 1
            path = os.path.join(OUT, f"{i:02d}_{level}_{safe_filename(p.get('name',''))}.pdf")
            try:
                to_pdf(p, path)
                print("banaya:", path)
            except Exception as e:
                print(f"[skip] {p.get('name')} -> {e}")
    print(f"\n{i} resumes {OUT} mein tayyar hain")


if __name__ == "__main__":
    main()