import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

# ---------------- CONFIGURATION ----------------
st.set_page_config(
    page_title="Smart Sewer Monitoring",
    page_icon="🌊",
    layout="wide"
)

FOLDER = Path(__file__).resolve().parent
LIVE_FILE = FOLDER / "smart_sewer_live_predictions.csv"

GAS_THRESHOLD = 1500
HEAVY_RAIN_THRESHOLD = 80
LOW_FLOW_THRESHOLD = 0.3
HIGH_WATER_THRESHOLD = 95
RISE_RATE_THRESHOLD = 5.0  # percentage points per minute

# ---------------- STYLING ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&display=swap');

html, body, [class*="css"]  {
    font-family: 'Poppins', sans-serif;
}

.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}

/* ---- Animated gradient header ---- */
.main-header {
    background: linear-gradient(-45deg, #0f2027, #203a43, #2c5364, #0f4c75);
    background-size: 400% 400%;
    animation: gradientShift 10s ease infinite;
    padding: 28px 32px;
    border-radius: 18px;
    margin-bottom: 20px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
}
@keyframes gradientShift {
    0% {background-position: 0% 50%;}
    50% {background-position: 100% 50%;}
    100% {background-position: 0% 50%;}
}
.main-header h1 {
    color: #ffffff;
    font-weight: 800;
    font-size: 2.3rem;
    margin-bottom: 4px;
}
.main-header p {
    color: #d8e9f0;
    font-size: 1rem;
    margin: 0;
}

/* ---- Metric cards ---- */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(44,83,100,0.12), rgba(15,76,117,0.10));
    border: 1px solid rgba(44,83,100,0.25);
    padding: 18px;
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 20px rgba(0,0,0,0.15);
}

/* ---- Section headers ---- */
.section-title {
    font-size: 1.4rem;
    font-weight: 700;
    margin-top: 10px;
    margin-bottom: 6px;
    padding-bottom: 6px;
    border-bottom: 3px solid #2c5364;
    display: inline-block;
}

/* ---- Status badges ---- */
.status-badge {
    display: inline-block;
    padding: 10px 20px;
    border-radius: 999px;
    font-weight: 700;
    font-size: 1rem;
    text-align: center;
    box-shadow: 0 4px 10px rgba(0,0,0,0.15);
}
.badge-green {
    background: linear-gradient(135deg, #11998e, #38ef7d);
    color: white;
}
.badge-yellow {
    background: linear-gradient(135deg, #f7971e, #ffd200);
    color: #2b2b2b;
}
.badge-red {
    background: linear-gradient(135deg, #cb2d3e, #ef473a);
    color: white;
}

/* ---- Info/warning/error boxes nicer ---- */
div[data-testid="stAlert"] {
    border-radius: 12px;
}

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f2027, #203a43);
}
section[data-testid="stSidebar"] * {
    color: #f0f4f8 !important;
}

/* ---- DataFrame ---- */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ----------------
st.markdown("""
<div class="main-header">
    <h1>🌊 Smart Sewer Monitoring System</h1>
    <p>Live drainage monitoring • Rise-rate analysis • Blockage detection • Worker safety</p>
</div>
""", unsafe_allow_html=True)


# ---------------- DECISION ENGINE ----------------
def analyze_sensors(z1, z2, z3, flow, rain, gas, rise_rates):
    levels = {"Zone 1": z1, "Zone 2": z2, "Zone 3": z3}

    high_rain = rain >= HEAVY_RAIN_THRESHOLD
    low_flow = flow <= LOW_FLOW_THRESHOLD

    # Rain can explain high levels only when all zones are high
    # and flow is not abnormally low.
    rain_explains_levels = (
        high_rain
        and min(z1, z2, z3) >= 90
        and not low_flow
    )

    blockage_zone = None
    reasons = []

    if not rain_explains_levels:
        # High level plus low flow is evidence of possible blockage.
        for zone, level in levels.items():
            if level >= HIGH_WATER_THRESHOLD and low_flow:
                blockage_zone = zone
                reasons.append(
                    f"{zone}: high water level with low flow"
                )
                break

        # High isolated level may indicate a local obstruction.
        if blockage_zone is None:
            for zone, level in levels.items():
                other_levels = [
                    v for k, v in levels.items() if k != zone
                ]
                if level >= HIGH_WATER_THRESHOLD and (
                    level - max(other_levels) >= 20
                ):
                    blockage_zone = zone
                    reasons.append(
                        f"{zone}: unusually high level compared "
                        "with the other zones"
                    )
                    break

        # A rapid rise is an additional warning signal.
        if blockage_zone is None:
            for zone, rate in rise_rates.items():
                if rate is not None and rate >= RISE_RATE_THRESHOLD:
                    blockage_zone = zone
                    reasons.append(
                        f"{zone}: rapid water-level rise "
                        f"({rate:.2f} percentage points/min)"
                    )
                    break

    if blockage_zone:
        blockage_status = "DETECTED"
        blockage_reason = "; ".join(reasons)
    elif rain_explains_levels:
        blockage_status = "NORMAL"
        blockage_reason = (
            "High levels across all zones may be rain-related; "
            "flow is not below the low-flow threshold."
        )
    else:
        blockage_status = "NORMAL"
        blockage_reason = "No configured blockage rule was triggered."

    # Gas is a separate safety override.

    # Blockage status is based on the decision made above.
    blockage_detected = blockage_zone is not None

    # Gas is a separate safety override.
    gas_detected = gas > GAS_THRESHOLD

    if gas_detected:
        gas_status = "CRITICAL - GAS HAZARD"
        worker_safety = "NOT PERMITTED"
        overall_status = "CRITICAL - DO NOT ENTER"

    elif max(z1, z2, z3) >= HIGH_WATER_THRESHOLD:
        gas_status = "SAFE GAS READING"
        worker_safety = "NOT PERMITTED"
        overall_status = "WARNING - HIGH WATER"

    elif blockage_detected:
        gas_status = "SAFE GAS READING"
        worker_safety = "PERMITTED - BLOCKAGE WORK"
        overall_status = "WARNING - BLOCKAGE DETECTED"

    else:
        gas_status = "SAFE GAS READING"
        worker_safety = "PERMITTED"
        overall_status = "NORMAL"

    return {
        "blockage_status": blockage_status,
        "blockage_zone": blockage_zone or "None identified",
        "blockage_reason": blockage_reason,
        "gas_status": gas_status,
        "gas_detected": gas_detected,
        "worker_safety": worker_safety,
        "overall_status": overall_status,
        "rain_explains_levels": rain_explains_levels,
    }


# ---------------- RISE RATE ----------------
def calculate_rise_rates(history):
    result = {
        "Zone 1": None,
        "Zone 2": None,
        "Zone 3": None,
    }

    if history is None or len(history) < 2:
        return result

    required = ["timestamp", "zone1", "zone2", "zone3"]
    if not all(c in history.columns for c in required):
        return result

    recent = history[required].copy()
    recent["timestamp"] = pd.to_datetime(
        recent["timestamp"], errors="coerce"
    )
    recent = recent.dropna(subset=["timestamp"])
    recent = recent.sort_values("timestamp")

    if len(recent) < 2:
        return result

    first = recent.iloc[-2]
    last = recent.iloc[-1]
    minutes = (
        last["timestamp"] - first["timestamp"]
    ).total_seconds() / 60

    if minutes <= 0:
        return result

    for zone, col in [
        ("Zone 1", "zone1"),
        ("Zone 2", "zone2"),
        ("Zone 3", "zone3"),
    ]:
        result[zone] = (
            float(last[col]) - float(first[col])
        ) / minutes

    return result


# ---------------- HELPER: BADGE RENDERER ----------------
def status_badge(text, level="green"):
    css_class = {
        "green": "badge-green",
        "yellow": "badge-yellow",
        "red": "badge-red",
    }.get(level, "badge-green")
    st.markdown(
        f'<span class="status-badge {css_class}">{text}</span>',
        unsafe_allow_html=True
    )


# ---------------- DATA SOURCE ----------------
st.sidebar.markdown("## 🛠️ Data Source")
mode = st.sidebar.radio(
    "Choose input",
    ["Live CSV", "Test scenarios", "Manual input"]
)

history = None

if mode == "Live CSV":
    if LIVE_FILE.exists():
        try:
            history = pd.read_csv(LIVE_FILE)
            if history.empty:
                st.warning("The live CSV is empty. Choose another input mode.")
                st.stop()
            latest = history.iloc[-1]

            required = [
                "zone1", "zone2", "zone3",
                "flow", "rain", "gas_raw_adc"
            ]
            missing = [c for c in required if c not in history.columns]
            if missing:
                st.error(f"Missing required columns: {missing}")
                st.stop()

            z1, z2, z3 = (
                float(latest["zone1"]),
                float(latest["zone2"]),
                float(latest["zone3"]),
            )
            flow = float(latest["flow"])
            rain = float(latest["rain"])
            gas = float(latest["gas_raw_adc"])

            st.caption(
                f"🕒 Latest recorded timestamp: "
                f"**{latest.get('timestamp', 'Unknown')}**"
            )
            if st.sidebar.button("🔄 Refresh readings"):
                st.rerun()

        except Exception as exc:
            st.error(f"Could not read live CSV: {exc}")
            st.stop()
    else:
        st.error(f"Live CSV not found: {LIVE_FILE}")
        st.info("Start mqtt_subscriber.py or select Test scenarios.")
        st.stop()

elif mode == "Test scenarios":
    scenario = st.sidebar.selectbox(
        "Select scenario",
        [
            "Scenario 1 - Normal",
            "Scenario 2 - Zone 1 blockage",
            "Scenario 3 - High rain",
            "Scenario 4 - High rain + low flow",
        ]
    )

    scenarios = {
        "Scenario 1 - Normal": (76, 68, 70, 0.5, 10, 0),
        "Scenario 2 - Zone 1 blockage": (98, 68, 70, 0.5, 10, 0),
        "Scenario 3 - High rain": (98, 98, 95, 0.5, 89, 0),
        "Scenario 4 - High rain + low flow": (98, 92, 95, 0.2, 89, 0),
    }

    z1, z2, z3, flow, rain, gas = scenarios[scenario]

    # Scenario tests have no time series unless one is supplied.
    history = None

else:
    st.sidebar.markdown("### 📟 Sensor Values")
    z1 = st.sidebar.number_input("Zone 1 level (%)", 0.0, 100.0, 76.0)
    z2 = st.sidebar.number_input("Zone 2 level (%)", 0.0, 100.0, 68.0)
    z3 = st.sidebar.number_input("Zone 3 level (%)", 0.0, 100.0, 70.0)
    flow = st.sidebar.number_input("Flow (L/min)", 0.0, 1000.0, 0.5)
    rain = st.sidebar.number_input("Rain intensity", 0.0, 100.0, 10.0)
    gas = st.sidebar.number_input("Gas raw ADC", 0, 4095, 0)

rise_rates = calculate_rise_rates(history)

# If a sensor input mode has no history, rates remain unknown.
result = analyze_sensors(
    z1, z2, z3, flow, rain, gas, rise_rates
)

# ---------------- LIVE METRICS ----------------
st.markdown('<div class="section-title">📊 Current Sensor Readings</div>', unsafe_allow_html=True)
st.write("")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🟦 Zone 1", f"{z1:.1f}%")
c2.metric("🟩 Zone 2", f"{z2:.1f}%")
c3.metric("🟨 Zone 3", f"{z3:.1f}%")
c4.metric("💧 Flow", f"{flow:.2f} L/min")
c5.metric("🌧️ Rain", f"{rain:.1f}")

st.divider()


# ---------------- BLOCKAGE ----------------
st.markdown('<div class="section-title">🚧 Blockage Analysis</div>', unsafe_allow_html=True)
st.write("")

b1, b2 = st.columns(2)
with b1:
    st.markdown("**Blockage Status**")
    status_badge(
        result["blockage_status"],
        "red" if result["blockage_status"] == "DETECTED" else "green"
    )
with b2:
    st.markdown("**Suspected Location**")
    st.markdown(f"### 📍 {result['blockage_zone']}")

st.write("")
st.info(result["blockage_reason"])

if result["rain_explains_levels"]:
    st.warning(
        "⚠️ High-rain explanation applied. This does not guarantee "
        "that a blockage is absent."
    )

st.divider()

# ---------------- SAFETY ----------------
st.markdown('<div class="section-title">🛡️ Safety and Hazard Status</div>', unsafe_allow_html=True)
st.write("")

s1, s2, s3 = st.columns(3)

with s1:
    st.markdown("**☣️ Gas Status**")
    status_badge(
        result["gas_status"],
        "red" if result["gas_detected"] else "green"
    )

with s2:
    st.markdown("**👷 Worker Safety**")
    safety_level = "green" if result["worker_safety"] in ("PERMITTED",) else (
        "yellow" if "BLOCKAGE" in result["worker_safety"] else "red"
    )
    status_badge(result["worker_safety"], safety_level)

with s3:
    st.markdown("**📋 Overall Status**")
    if result["overall_status"].startswith("CRITICAL"):
        overall_level = "red"
    elif result["overall_status"].startswith("WARNING"):
        overall_level = "yellow"
    else:
        overall_level = "green"
    status_badge(result["overall_status"], overall_level)

st.write("")

if result["gas_detected"]:
    st.error(
        f"🚨 Gas ADC reading {gas:.0f} exceeds threshold "
        f"{GAS_THRESHOLD}. Human entry is NOT PERMITTED."
    )
elif result["worker_safety"] == "NOT PERMITTED":
    st.error(
        "🚫 Entry is not permitted under the configured water-level "
        "or blockage rules."
    )
else:
    st.warning(
        "⚠️ A low gas reading alone does not establish that a sewer is safe. "
        "Follow approved site procedures and use calibrated safety equipment."
    )

# ---------------- HISTORY ----------------
if history is not None and not history.empty:
    st.divider()
    st.markdown('<div class="section-title">📈 Recent Sensor History</div>', unsafe_allow_html=True)
    st.write("")
    st.dataframe(history.tail(20), use_container_width=True)

    if all(c in history.columns for c in ["timestamp", "zone1", "zone2", "zone3"]):
        chart_data = history.copy()
        chart_data["timestamp"] = pd.to_datetime(
            chart_data["timestamp"], errors="coerce"
        )
        chart_data = chart_data.dropna(subset=["timestamp"])
        chart_data = chart_data.sort_values("timestamp").tail(100)

        if not chart_data.empty:
            st.markdown('<div class="section-title">📉 Water Levels Over Time</div>', unsafe_allow_html=True)
            st.write("")
            st.line_chart(
                chart_data.set_index("timestamp")[["zone1", "zone2", "zone3"]]
            )

st.divider()
st.caption(
    "⚙️ Prototype decision support only. Synthetic model results and these "
    "rules are not certified for real-world sewer-entry safety."
)