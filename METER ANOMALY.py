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

    result = reader.readtext(
        gray,
        detail=1
    )

    texts = []

    for item in result:
        texts.append(item[1])

    return "\n".join(texts)


def read_accuracy_image(uploaded_file):

    reader = load_reader()

    image = Image.open(uploaded_file)

    img_np = np.array(image)

    gray = cv2.cvtColor(
        img_np,
        cv2.COLOR_RGB2GRAY
    )

    gray = cv2.resize(
        gray,
        None,
        fx=3,
        fy=3,
        interpolation=cv2.INTER_CUBIC
    )

    gray = cv2.GaussianBlur(
        gray,
        (3,3),
        0
    )

    gray = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2
    )

    result = reader.readtext(
        gray,
        detail=1
    )

    texts = []

    for item in result:
        texts.append(item[1])

    return "\n".join(texts)


# =====================================
# PARSE ERROR %
# =====================================

def extract_error(text):

    if not text:
        return None

    text = text.replace(",", ".")

    matches = re.findall(
        r'-?\d+\.\d+',
        text
    )

    for m in matches:

        try:

            value = float(m)

            if -100 <= value <= 100:
                return value

        except:
            pass

    return None


# =====================================
# PARSE METER VALUES
# =====================================

def parse_meter_values(text):

    data = {}

    if not text:
        return data

    text = text.upper()

    text = text.replace(",", ".")

    # OCR corrections from your screenshots

    text = text.replace("UX:", "U3:")
    text = text.replace("II:", "I1:")
    text = text.replace("PFI:", "PF1:")
    text = text.replace("PFA:", "PF3:")

    # Voltage

    u1 = re.search(
        r'U1[: ]*(\d+\.\d+)',
        text
    )

    u2 = re.search(
        r'U2[: ]*(\d+\.\d+)',
        text
    )

    u3 = re.search(
        r'U3[: ]*(\d+\.\d+)',
        text
    )

    if u1:
        data["u1"] = float(u1.group(1))

    if u2:
        data["u2"] = float(u2.group(1))

    if u3:
        data["u3"] = float(u3.group(1))

    # Current

    i1 = re.search(
        r'I1[: ]*(\d+\.\d+)',
        text
    )

    i2 = re.search(
        r'I2[: ]*(\d+\.\d+)',
        text
    )

    i3 = re.search(
        r'I3[: ]*(\d+\.\d+)',
        text
    )

    if i1:
        data["i1"] = float(i1.group(1))

    if i2:
        data["i2"] = float(i2.group(1))

    if i3:
        data["i3"] = float(i3.group(1))

    # PF

    pf1 = re.search(
        r'PF1[: ]*(-?\d+\.\d+)',
        text
    )

    pf2 = re.search(
        r'PF2[: ]*(-?\d+\.\d+)',
        text
    )

    pf3 = re.search(
        r'PF3[: ]*(-?\d+\.\d+)',
        text
    )

    if pf1:
        data["pf1"] = float(pf1.group(1))

    if pf2:
        data["pf2"] = float(pf2.group(1))

    if pf3:
        data["pf3"] = float(pf3.group(1))

    total_pf = re.search(
        r'PF[: ]*(\d+\.\d+)',
        text
    )

    if total_pf:
        data["pf_total"] = float(
            total_pf.group(1)
        )

    # Frequency

    lines = text.split("\n")

    for line in lines:

        line = line.strip()

        if line.startswith("F:"):

            try:

                freq = float(
                    line.split(":")[1]
                )

                if 55 <= freq <= 65:

                    freq = 50 + (
                        freq - int(freq)
                    )

                data["freq"] = round(
                    freq,
                    2
                )

            except:
                pass

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

    pf_values = []

    for pf_name, value in {
        "PF1": pf1,
        "PF2": pf2,
        "PF3": pf3
    }.items():

        if value is not None:

            pf_values.append(value)

            if value < 0:

                findings.append(
                    f"{pf_name} negative ({value})"
                )

                scores["CT Polarity Reversed"] += 35

    if len(pf_values) == 3:

        spread = max(pf_values) - min(pf_values)

        if spread > 0.30:

            findings.append(
                f"Large PF variation ({spread:.3f})"
            )

            scores["Wrong Phase Association"] += 40

            scores["Installation Wiring Issue"] += 20

        avg_pf = sum(
            abs(x) for x in pf_values
        ) / 3

        if avg_pf < 0.85:

            findings.append(
                f"PF below ESAH reference ({avg_pf:.3f})"
            )

            scores["Low Power Factor Load"] += 30

    if freq is not None:

        if freq < 49 or freq > 51:

            findings.append(
                f"Abnormal Frequency ({freq}Hz)"
            )

            scores["Test Set Error"] += 10

    if complaint_type == "High Bill":

        scores["Customer Load Increase"] += 35

    scores = {
        k: max(v, 0)
        for k, v in scores.items()
    }

    total = sum(scores.values())

    ranked = []

    for cause, value in scores.items():

        probability = round(
            value / total * 100,
            1
        )

        ranked.append(
            (cause, probability)
        )

    ranked.sort(
        key=lambda x: x[1],
        reverse=True
    )

    customer_response = """
Investigation completed.

Please refer to engineering assessment below.
"""

    top_cause = ranked[0][0]

    if top_cause == "CT Polarity Reversed":

        recommendations.extend([
            "Verify CT polarity",
            "Verify current lead orientation",
            "Repeat vector test"
        ])

    elif top_cause == "Wrong Phase Association":

        recommendations.extend([
            "Verify phase sequence",
            "Verify V-I pairing",
            "Repeat phase angle verification"
        ])

    else:

        recommendations.append(
            "Further site verification recommended"
        )

    return (
        findings,
        ranked,
        recommendations,
        customer_response
    )
# =====================================
# DETAILED ENGINEERING REPORT
# =====================================

def generate_detailed_report(
    meter_data,
    error_value,
    ranked,
    complaint_type
):

    u1 = meter_data.get("u1","N/A")
    u2 = meter_data.get("u2","N/A")
    u3 = meter_data.get("u3","N/A")

    i1 = meter_data.get("i1","N/A")
    i2 = meter_data.get("i2","N/A")
    i3 = meter_data.get("i3","N/A")

    pf1 = meter_data.get("pf1","N/A")
    pf2 = meter_data.get("pf2","N/A")
    pf3 = meter_data.get("pf3","N/A")

    freq = meter_data.get("freq","N/A")

    report = f"""
# Site Technical Assessment

## Meter Accuracy

Accuracy Result:

{error_value} %

"""

    if error_value is not None:

        if abs(error_value) <= 0.5:

            report += """
Meter accuracy remains within acceptable tolerance.

Current evidence does not indicate meter over-registration.

"""

        else:

            report += """
Meter accuracy requires further investigation.

Potential metering error cannot be ruled out.

"""

    report += f"""

## Voltage Analysis

U1 = {u1} V
U2 = {u2} V
U3 = {u3} V

Voltage profile appears relatively balanced.

## Current Analysis

I1 = {i1}
I2 = {i2}
I3 = {i3}

Current profile appears relatively balanced.

## Power Factor Analysis

PF1 = {pf1}
PF2 = {pf2}
PF3 = {pf3}

"""

    if isinstance(pf3,(float,int)) and pf3 < 0:

        report += """
Negative power factor detected.

Possible causes:

• CT polarity reversal
• Wrong phase-current pairing
• Incorrect test lead connection
• Wiring anomaly

"""

    report += f"""

## Frequency

Frequency Recorded:

{freq} Hz

"""

    if ranked:

        report += """

## Root Cause Probability

"""

        for cause, prob in ranked:

            report += f"""
• {cause} : {prob}%
"""

    report += f"""

## Customer Complaint Assessment

Complaint Type:

{complaint_type}

"""

    if complaint_type == "High Bill":

        report += """

Current evidence suggests the meter is measuring within tolerance (where accuracy is acceptable).

Investigation should focus on:

• Additional customer load
• Air conditioning usage
• Water heaters
• Industrial equipment
• Low power factor equipment
• Installation wiring condition

"""

    report += """

## Likely Customer Question

"Is my meter faulty because the power factor is low?"

## Suggested Technician Response

The power factor readings indicate abnormal operating conditions.

However, the meter accuracy verification should be considered separately.

Where accuracy remains within allowable tolerance, there is currently insufficient evidence to conclude that the meter is over-registering energy consumption.

The abnormal power factor may instead be associated with wiring conditions, CT polarity, phase-current relationship, connected equipment characteristics or installation issues.

Further investigation is recommended before concluding that the meter is faulty.

"""

    return report
# =====================================
# OCR VERIFICATION
# =====================================

def verify_ocr_values(meter_data, error_value):

    st.subheader("OCR Verification")

    st.caption(
        "Verify OCR readings before running analysis."
    )

    col1, col2 = st.columns(2)

    with col1:

        u1 = st.number_input(
            "U1 (V)",
            value=float(meter_data.get("u1", 0))
        )

        u2 = st.number_input(
            "U2 (V)",
            value=float(meter_data.get("u2", 0))
        )

        u3 = st.number_input(
            "U3 (V)",
            value=float(meter_data.get("u3", 0))
        )

        i1 = st.number_input(
            "I1 (A)",
            value=float(meter_data.get("i1", 0))
        )

        i2 = st.number_input(
            "I2 (A)",
            value=float(meter_data.get("i2", 0))
        )

        i3 = st.number_input(
            "I3 (A)",
            value=float(meter_data.get("i3", 0))
        )

    with col2:

        pf1 = st.number_input(
            "PF1",
            value=float(meter_data.get("pf1", 0))
        )

        pf2 = st.number_input(
            "PF2",
            value=float(meter_data.get("pf2", 0))
        )

        pf3 = st.number_input(
            "PF3",
            value=float(meter_data.get("pf3", 0))
        )

        freq = st.number_input(
            "Frequency (Hz)",
            value=float(meter_data.get("freq", 50))
        )

        accuracy = st.number_input(
            "Accuracy Error (%)",
            value=float(error_value or 0)
        )

    # ==========================
    # Engineering Validation
    # ==========================

    if freq < 49 or freq > 51:
        st.warning(
            f"Frequency ({freq}Hz) appears abnormal. Please verify."
        )

    for phase, value in {
        "U1": u1,
        "U2": u2,
        "U3": u3
    }.items():

        if value < 100 or value > 300:
            st.warning(
                f"{phase} appears suspicious ({value}V)"
            )

    for pf_name, value in {
        "PF1": pf1,
        "PF2": pf2,
        "PF3": pf3
    }.items():

        if value < -1 or value > 1:
            st.warning(
                f"{pf_name} appears suspicious ({value})"
            )

    verified_data = {
        "u1": u1,
        "u2": u2,
        "u3": u3,
        "i1": i1,
        "i2": i2,
        "i3": i3,
        "pf1": pf1,
        "pf2": pf2,
        "pf3": pf3,
        "freq": freq
    }

    return verified_data, accuracy
# =====================================
# OCR PROCESSING
# =====================================

if actual_img and error_img:

    with st.spinner("Performing OCR..."):

        actual_text = read_image(actual_img)

        error_text = read_accuracy_image(error_img)

        meter_data = parse_meter_values(
            actual_text
        )

        error_value = extract_error(
            error_text
        )

        # DEBUG OUTPUTS

        st.subheader("METER DATA")
        st.json(meter_data)

        st.subheader("ACCURACY OCR")
        st.text(error_text)

    st.success(
        "OCR Extraction Completed"
    )


    with st.expander(
        "View Raw OCR Output"
    ):
        st.subheader("Parsed Meter Data")

        st.json(meter_data)

        st.text(actual_text)

        st.text(error_text)

    verified_data, verified_error = verify_ocr_values(
        meter_data,
        error_value
    )

    if st.button(
        "✅ Confirm Readings"
    ):

        st.session_state["verified"] = True

        st.session_state["verified_data"] = verified_data

        st.session_state["verified_error"] = verified_error

# =====================================
# RUN INVESTIGATION
# =====================================

if st.session_state.get("verified"):

    if st.button(
        "🔍 Run Investigation",
        type="primary"
    ):

        meter_data = st.session_state[
            "verified_data"
        ]

        error_value = st.session_state[
            "verified_error"
        ]

        findings, ranked, recommendations, customer_response = analyze_meter(
            meter_data,
            error_value,
            meter_class,
            meter_type,
            complaint_type
        )

        detailed_report = generate_detailed_report(
            meter_data,
            error_value,
            ranked,
            complaint_type
        )

        st.success(
            "Investigation Completed"
        )

        st.divider()

        st.header("Technical Findings")

        for item in findings:
            st.write("✅", item)

        st.divider()

        st.header("Root Cause Probability")

        for cause, prob in ranked:

            st.write(
                f"**{cause}: {prob}%**"
            )

            st.progress(
                prob / 100
            )

        st.divider()

        st.header("Recommended Actions")

        for item in recommendations:

            st.write(
                "🔧",
                item
            )

        st.divider()

        st.header(
            "Customer Anticipation Response"
        )

        st.info(
            customer_response
        )

        st.divider()

        st.header(
            "Full Engineering Assessment"
        )

        st.markdown(
            detailed_report
        )