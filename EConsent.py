# streamlit_app.py
# FULL APP : Thai E-Consent
# Streamlit + Supabase + Signatures + PDF + Admin Dashboard
# pip install streamlit supabase reportlab pytz pandas streamlit-drawable-canvas pillow

import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
import pytz
import base64
import io
from PIL import Image
from streamlit_drawable_canvas import st_canvas

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Thai E-Consent", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BKK = pytz.timezone("Asia/Bangkok")

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

# ---------------- HELPERS ----------------
def now_bkk():
    return datetime.now(BKK).strftime("%Y-%m-%d %H:%M:%S")

def sig_pad(label, key):
    st.markdown(f"### {label}")
    canvas = st_canvas(
        stroke_width=2,
        stroke_color="#000000",
        background_color="#FFFFFF",
        height=180,
        width=500,
        drawing_mode="freedraw",
        key=key
    )

    if canvas.image_data is not None:
        img = Image.fromarray(canvas.image_data.astype("uint8"))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    return None

def decode_sig(sig64, filename):
    data = base64.b64decode(sig64)
    with open(filename, "wb") as f:
        f.write(data)

def create_pdf(record):
    filename = "/tmp/consent.pdf"

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "STSong-Light"

    story = []

    story.append(Paragraph("ใบยินยอมทำหัตถการ", styles["Title"]))
    story.append(Spacer(1,12))

    for k,v in record.items():
        if "signature" not in k:
            story.append(Paragraph(f"{k}: {v}", styles["Normal"]))
            story.append(Spacer(1,6))

    for sig in ["patient_signature","doctor_signature","nurse_signature"]:
        if record.get(sig):
            imgfile = f"/tmp/{sig}.png"
            decode_sig(record[sig], imgfile)
            story.append(Paragraph(sig, styles["Normal"]))
            story.append(RLImage(imgfile, width=200, height=80))
            story.append(Spacer(1,8))

    doc.build(story)
    return filename

# ---------------- MENU ----------------
menu = st.sidebar.radio(
    "Menu",
    ["Patient Consent Form", "Admin Dashboard"]
)

# ===================================================
# PATIENT PAGE
# ===================================================
if menu == "Patient Consent Form":

    st.title("📄 ระบบยินยอมทำหัตถการ")

    with st.form("consent"):

        c1, c2 = st.columns(2)

        with c1:
            patient_id = st.text_input("HN / เลขบัตร")
            patient_name = st.text_input("ชื่อผู้ป่วย")
            age = st.number_input("อายุ",1,120,20)

        with c2:
            doctor_name = st.text_input("แพทย์")
            nurse_name = st.text_input("พยาบาลพยาน")
            procedure = st.selectbox(
                "หัตถการ",
                ["Ankle Block", "Brachial Block"]
            )

        st.markdown("---")

        if procedure == "Ankle Block":
            st.info("""
การฉีดยาชาบริเวณข้อเท้าเพื่อทำแผล

ความเสี่ยง:
- เจ็บ
- ชา
- เลือดออก
- ติดเชื้อ
- แพ้ยา
""")
        else:
            st.info("""
การฉีดยาชาบริเวณแขนเพื่อทำแผลมือ

ความเสี่ยง:
- เจ็บ
- ชา/อ่อนแรงชั่วคราว
- เลือดออก
- แพ้ยา
- เส้นประสาทบาดเจ็บ (พบน้อย)
""")

        agree = st.checkbox("ข้าพเจ้ายินยอม")

        st.markdown("---")

        patient_sig = sig_pad("ผู้ป่วยเซ็นชื่อ", "p")
        doctor_sig = sig_pad("แพทย์เซ็นชื่อ", "d")
        nurse_sig = sig_pad("พยาบาลพยานเซ็นชื่อ", "n")

        submit = st.form_submit_button("💾 Save")

    if submit:

        ts = now_bkk()

        rec = {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "age": age,
            "doctor_name": doctor_name,
            "nurse_name": nurse_name,
            "procedure": procedure,
            "agree": agree,
            "timestamp_bkk": ts,
            "patient_signature": patient_sig,
            "doctor_signature": doctor_sig,
            "nurse_signature": nurse_sig
        }

        supabase.table("consent_records").insert(rec).execute()

        st.success("Saved")

        pdf = create_pdf(rec)

        with open(pdf,"rb") as f:
            st.download_button(
                "📄 Download PDF",
                f,
                file_name=f"{patient_id}_consent.pdf",
                mime="application/pdf"
            )

# ===================================================
# ADMIN PAGE
# ===================================================
if menu == "Admin Dashboard":

    st.title("📊 Admin Dashboard")

    data = supabase.table("consent_records").select("*").execute()

    rows = data.data

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode()

        st.download_button(
            "⬇️ Export CSV",
            csv,
            "consents.csv",
            "text/csv"
        )

        st.metric("Total Consents", len(df))

        st.bar_chart(df["procedure"].value_counts())

    else:
        st.info("No data")