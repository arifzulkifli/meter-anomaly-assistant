import streamlit as st
import easyocr
import cv2
import numpy as np
from PIL import Image
import re

# =====================================
# PAGE CONFIG
# =====================================

st.set_page_config(
    page_title="Meter Fault Assistant",
    layout="wide"
)

st.title("⚡ Meter Fault Assistant")

# =====================================
# CACHE OCR
# =====================================

@st.cache_resource
def load_reader():
    return easyocr.Reader(['en'], gpu=False)

# =====================================
# USER INPUTS
# =====================================

col1, col2 = st.columns(2)

with col1:

    installation = st.text_input(
        "Installation Number"
    )

    meter_serial = st.text_input(
        "Meter Serial Number"
    )

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
    complaint_type = st.selectbox(
        "Customer Complaint",
        [
            "High Bill",
            "Meter Fault",
            "Low Consumption",
            "Intermittent Supply",
            "Routine Testing"
        ]
    )
# =====================================
# IMAGE UPLOAD
# =====================================

actual_img = st.file_uploader(
    "Upload Actual Values Screen",
    type=["png", "jpg", "jpeg"]
)

error_img = st.file_uploader(
    "Upload Accuracy Screen",
    type=["png", "jpg", "jpeg"]
)

# =====================================
# OCR FUNCTION
# =====================================

def read_image(uploaded_file):

    reader = load_reader()

    image = Image.open(uploaded_file)

    img_np = np.array(image)

    gray = cv2.cvtColor(
        img_np,
        cv2.COLOR_RGB2GRAY
    )

    result = reader.readtext(gray)

    texts = []

    for item in result:

        texts.append(item[1])

    return "\n".join(texts)

# =====================================
# PARSE ERROR %
# =====================================

def extract_error(text):

    text = text.replace(",", ".")

    matches = re.findall(
        r'-?\d+\.\d+\s*%',
        text
    )

    if matches:

        try:

            return float(
                matches[0]
                .replace("%", "")
                .strip()
            )

        except:
            pass

    return None

# =====================================
# METER VALUE PARSER
# =====================================

def parse_meter_values(text):

    data = {}

    if text is None:
        return {}

    text = text.replace("\n", " ")

    patterns = {
        "u1": r"U1[: ]*([0-9]+\.?[0-9]*)",
        "u2": r"U2[: ]*([0-9]+\.?[0-9]*)",
        "u3": r"U3[: ]*([0-9]+\.?[0-9]*)",

        "i1": r"I1[: ]*([0-9]+\.?[0-9]*)",
        "i2": r"I2[: ]*([0-9]+\.?[0-9]*)",
        "i3": r"I3[: ]*([0-9]+\.?[0-9]*)",

        "pf1": r"PF1[: ]*(-?[0-9]+\.?[0-9]*)",
        "pf2": r"PF2[: ]*(-?[0-9]+\.?[0-9]*)",
        "pf3": r"PF3[: ]*(-?[0-9]+\.?[0-9]*)",
    }

    for key, pattern in patterns.items():

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            try:
                data[key] = float(match.group(1))
            except:
                pass

    freq_match = re.search(
        r'([4-6][0-9]\.[0-9]+)\s*Hz',
        text,
        re.IGNORECASE
    )

    if freq_match:

        data["freq"] = float(
            freq_match.group(1)
        )

    return data

# =====================================
# ANALYSIS ENGINE
# =====================================

def analyze_meter(
    data,
    error_value,
    meter_class,
    meter_type,
    complaint_type
):

    findings = []
    recommendations = []
    scores = {
        "Meter Internal Fault": 10,
        "CT Polarity Reversed": 10,
        "Wrong Phase Association": 10,
        "Low Power Factor Load": 10,
        "Customer Load Increase": 10,
        "Installation Wiring Issue": 10,
        "Test Set Error": 10
    }

    pf1 = data.get("pf1")
    pf2 = data.get("pf2")
    pf3 = data.get("pf3")

    freq = data.get("freq")

    # -------------------------
    # Accuracy
    # -------------------------

    if error_value is not None:

        if abs(error_value) <= 0.5:

            findings.append(
                f"Meter accuracy acceptable ({error_value:.2f}%)"
            )

            scores["Meter Internal Fault"] -= 20

        elif abs(error_value) <= 1:

            findings.append(
                f"Meter accuracy marginal ({error_value:.2f}%)"
            )

            scores["Meter Internal Fault"] += 20

        else:

            findings.append(
                f"Meter accuracy outside tolerance ({error_value:.2f}%)"
            )

            scores["Meter Internal Fault"] += 70

    # -------------------------
    # Power Factor
    # -------------------------

    negative_pf = 0

    for pf_name, value in {
        "PF1": pf1,
        "PF2": pf2,
        "PF3": pf3
    }.items():

        if value is not None:

            if value < 0:

                negative_pf += 1

                findings.append(
                    f"{pf_name} negative ({value})"
                )

                scores["CT Polarity Reversed"] += 35

    # -------------------------
    # PF Spread
    # -------------------------

    pf_values = []

    for x in [pf1, pf2, pf3]:

        if x is not None:
            pf_values.append(x)

    if len(pf_values) == 3:

        spread = max(pf_values) - min(pf_values)

        if spread > 0.30:

            findings.append(
                f"Large PF variation ({spread:.3f})"
            )

            scores["Wrong Phase Association"] += 40
            scores["Installation Wiring Issue"] += 20

        avg_pf = sum([
            abs(x)
            for x in pf_values
        ]) / 3

        if avg_pf < 0.85:

            findings.append(
                f"PF below ESAH reference ({avg_pf:.3f})"
            )

            scores["Low Power Factor Load"] += 30

    # -------------------------
    # Frequency
    # -------------------------

    if freq is not None:

        if freq < 49 or freq > 51:

            findings.append(
                f"Abnormal Frequency ({freq}Hz)"
            )

            scores["Test Set Error"] += 10

    # -------------------------
    # High Bill Logic
    # -------------------------

    if complaint_type == "High Bill":

        scores["Customer Load Increase"] += 35

        if error_value is not None:

            if abs(error_value) <= 0.5:

                scores["Customer Load Increase"] += 20
                scores["Meter Internal Fault"] -= 10

    # -------------------------
    # Probability
    # -------------------------

    scores = {
        k:max(v,0)
        for k,v in scores.items()
    }

    total = sum(scores.values())

    ranked = []

    for cause,value in scores.items():

        percentage = round(
            value / total * 100,
            1
        )

        ranked.append(
            (
                cause,
                percentage
            )
        )

    ranked.sort(
        key=lambda x:x[1],
        reverse=True
    )

    # -------------------------
    # Customer Explanation
    # -------------------------

    if error_value is not None and abs(error_value) <= 0.5:

        customer_response = f"""
Meter accuracy test recorded {error_value:.2f}% deviation.

This result is within acceptable limits and does not indicate meter over-registration.

Abnormal power factor conditions were detected during testing.

Low power factor may be caused by customer electrical equipment, wiring conditions, phase association issues, CT polarity issues or installation conditions.

Current evidence suggests further verification should focus on installation and load characteristics before concluding that the meter is faulty.
"""

    else:

        customer_response = """
Additional verification required before final conclusion.
"""

    recommendations = []

    top_cause = ranked[0][0]

    if top_cause == "CT Polarity Reversed":

        recommendations.extend([
            "Verify CT S1/S2 polarity",
            "Verify current lead orientation",
            "Repeat vector diagram test"
        ])

    elif top_cause == "Wrong Phase Association":

        recommendations.extend([
            "Verify phase sequence",
            "Verify V-I pairing",
            "Repeat phase angle verification"
        ])

    elif top_cause == "Low Power Factor Load":

        recommendations.extend([
            "Inspect motors",
            "Inspect compressors",
            "Inspect welding equipment",
            "Evaluate capacitor bank performance"
        ])

    return (
        findings,
        ranked,
        recommendations,
        customer_response
    )