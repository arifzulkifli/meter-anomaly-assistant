import streamlit as st
import easyocr
import cv2
import numpy as np
import pandas as pd
from PIL import Image
import re

# ==========================
# PAGE SETTINGS
# ==========================

st.set_page_config(
    page_title="Meter Test Assistant",
    layout="wide"
)

st.title("⚡ Meter Test Assistant MVP")

# ==========================
# USER INPUTS
# ==========================

col1, col2 = st.columns(2)

with col1:
    installation = st.text_input("Installation Number")

    meter_serial = st.text_input("Meter Serial Number")

    meter_type = st.selectbox(
        "Meter Type",
        [
            "3 Phase Direct",
            "3 Phase CT",
            "3 Phase CT/PT"
        ]
    )

with col2:

    meter_class = st.selectbox(
        "Meter Class",
        [
            "0.2S",
            "0.5S",
            "1.0",
            "2.0"
        ]
    )

    manufacturer = st.selectbox(
        "Manufacturer",
        [
            "EDMI",
            "Secure",
            "Hexing",
            "Landis+Gyr",
            "Others"
        ]
    )

# ==========================
# FILE UPLOAD
# ==========================

actual_img = st.file_uploader(
    "Upload Actual Values Screen",
    type=["jpg", "jpeg", "png"]
)

error_img = st.file_uploader(
    "Upload Error Measurement Screen",
    type=["jpg", "jpeg", "png"]
)

# ==========================
# OCR
# ==========================

reader = easyocr.Reader(['en'], gpu=False)


def read_image(uploaded_file):
    image = Image.open(uploaded_file)
    image_np = np.array(image)

    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)

    results = reader.readtext(gray)

    extracted = []

    for item in results:
        extracted.append(item[1])

    return "\n".join(extracted)


def extract_error(text):

    match = re.search(r'(-?\d+\.\d+)\s*%', text)

    if match:
        return float(match.group(1))

    return None


# ==========================
# ANOMALY ENGINE
# ==========================

def analyze(error_value):

    findings = []
    causes = []

    tolerance_map = {
        "0.2S": 0.2,
        "0.5S": 0.5,
        "1.0": 1.0,
        "2.0": 2.0
    }

    limit = tolerance_map[meter_class]

    if error_value is not None:

        if error_value < -limit:

            findings.append(
                f"Meter Under Registration ({error_value}%)"
            )

            causes.extend([
                "Meter drift",
                "Voltage circuit issue",
                "Current circuit issue"
            ])

        elif error_value > limit:

            findings.append(
                f"Meter Over Registration ({error_value}%)"
            )

            causes.extend([
                "Meter calibration issue",
                "Incorrect wiring"
            ])

        else:

            findings.append(
                f"Meter Accuracy Within Limit ({error_value}%)"
            )

    return findings, causes


# ==========================
# RUN ANALYSIS
# ==========================

if st.button("Analyze Meter"):

    if actual_img and error_img:

        with st.spinner("Running OCR..."):

            text1 = read_image(actual_img)
            text2 = read_image(error_img)

            error_value = extract_error(text2)

            findings, causes = analyze(error_value)

        st.success("Analysis Completed")

        tab1, tab2, tab3 = st.tabs(
            [
                "Assessment",
                "OCR Output",
                "Raw Data"
            ]
        )

        with tab1:

            st.subheader("Meter Assessment")

            st.write(
                f"Installation: {installation}"
            )

            st.write(
                f"Meter Serial: {meter_serial}"
            )

            st.write(
                f"Meter Type: {meter_type}"
            )

            st.write(
                f"Meter Class: {meter_class}"
            )

            st.write(
                f"Manufacturer: {manufacturer}"
            )

            st.write("---")

            st.subheader("Findings")

            for f in findings:
                st.write("✅", f)

            st.subheader("Possible Causes")

            for c in causes:
                st.write("•", c)

        with tab2:

            st.subheader("Actual Values OCR")

            st.text(text1)

            st.subheader("Error Screen OCR")

            st.text(text2)

        with tab3:

            st.write({
                "installation": installation,
                "meter_serial": meter_serial,
                "meter_type": meter_type,
                "meter_class": meter_class,
                "manufacturer": manufacturer,
                "error": error_value
            })

    else:

        st.warning(
            "Please upload both images."
        )