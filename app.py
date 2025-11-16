# app.py — Mechapres Industrial Heat Pump Calculator
# Simple HP model + Low/High case economic calculations (Excel-style), all in £

import math
from io import BytesIO
from datetime import datetime

import streamlit as st
import matplotlib as mpl
import matplotlib.pyplot as plt

mpl.rcParams["figure.facecolor"] = "none"
mpl.rcParams["axes.facecolor"] = "none"

MECHAPRES_COLORS = {
    "primary": "#003366",
    "accent":  "#1a9850",
    "text":    "#111111",
    "muted":   "#6b7280"
}
LOGO_PATH = "mechapres_logo.png"  # optional logo file next to app.py

# Fuel emission factors (kg CO2 per kWh, Net CV) from your tables
FUEL_EMISSION_FACTORS_KG_PER_KWH = {
    "Butane":            0.24107,
    "LNG":               0.20489,
    "LPG":               0.23032,
    "Natural gas":       0.20270,
    "Propane":           0.23258,
    "Fuel oil":          0.28523,
    "Coal (industrial)": 0.33944,
}
FUEL_OPTIONS = list(FUEL_EMISSION_FACTORS_KG_PER_KWH.keys())

# Electricity CO2 factor (kg CO2 per MWh) – used in background
ELECTRICITY_CO2_KG_PER_MWH = 50.0

# ----------------- Brand / Theme -----------------
def apply_brand_theme():
    css = """
    <style>
      :root {
        --mp-top:    #f8e6f1;
        --mp-mid:    #6e49b9;
        --mp-bottom: #ffe3c2;
        --mp-text:   #111111;
        --mp-card:   rgba(255,255,255,0.74);
        --mp-border: rgba(0,0,0,0.08);
      }
      html, body, .stApp {
        min-height: 100vh;
        background: linear-gradient(180deg, var(--mp-top) 0%, var(--mp-mid) 45%, var(--mp-bottom) 100%) fixed;
      }
      .main .block-container { padding-top: 1.0rem; padding-bottom: 2.5rem; background: transparent; }
      h1, h2, h3 { color: #ffffff !important; text-shadow: 0 1px 2px rgba(0,0,0,0.25); }
      .stButton>button, .stDownloadButton>button {
        background: #003366; color:#fff;border:none;border-radius:12px;padding:.5rem .9rem; box-shadow:0 4px 12px rgba(0,0,0,0.12);
      }
      .stButton>button:hover, .stDownloadButton>button:hover { filter: brightness(1.06); }
      section[data-testid="stSidebar"] { background: rgba(255,255,255,.55); backdrop-filter: blur(6px); border-right:1px solid var(--mp-border); }
      .stExpander, .stForm { background: var(--mp-card)!important; border:1px solid var(--mp-border); border-radius:14px; padding:.6rem .8rem; }
      .brandbar { background: transparent !important; border-bottom: 1px solid rgba(255,255,255,.25) !important; }
      .brandbar .tagline { color:#fff !important; text-shadow:0 1px 2px rgba(0,0,0,0.25); font-weight:600; }
      .stTextInput input:focus, .stNumberInput input:focus { outline:2px solid #1a9850; }
      a, a:visited { color:#003366; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def show_brand_bar(logo_path=LOGO_PATH, brand=MECHAPRES_COLORS):
    st.markdown("<style>.brandbar{ position:sticky; top:0; z-index:999; padding:10px 16px; }</style>", unsafe_allow_html=True)
    with st.container():
        st.markdown("<div class='brandbar'></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 4, 1.4])
        with c1:
            try:
                st.image(logo_path, width=130)
            except Exception:
                st.markdown("### **MECHAPRES**")
        with c2:
            st.markdown("<div class='tagline'>Industrial steam decarbonization, made simple.</div>", unsafe_allow_html=True)
        with c3:
            if st.button("Contact Sales", key="cta_top", use_container_width=True):
                st.session_state.show_contact = True

if "show_contact" not in st.session_state:
    st.session_state.show_contact = False
if "welcome_hint" not in st.session_state:
    st.session_state.welcome_hint = ""

# ----------------- Decision tree thresholds -----------------
DT_THRESHOLDS = {
    "process_temp_min": 80.0,  "process_temp_max": 200.0,
    "hp_target_max":    180.0, "steam_pressure_max": 10.0,
    "hot_air_ok_max":   110.0, "hot_air_caution_max": 150.0,
}

def evaluate_decision_tree(
    process_temp_c,
    energy_vector,
    target_supply_temp_c,
    steam_pressure_barA,
    has_waste_heat,
    waste_temp_known,
    waste_temp_c,
    waste_amount_known,
    waste_amount_pct_band,
    waste_heat_captured=None,
    has_waste_heat_processor=None,
    how_released=None,
    waste_form=None,
    humidity_ratio_known=None,
    q_waste_kw=None
):
    TH = DT_THRESHOLDS
    notes = []
    assumptions = {}

    # 1) Process temperature window
    if process_temp_c < TH["process_temp_min"] or process_temp_c > TH["process_temp_max"]:
        return {
            "status": "not_viable",
            "notes": [f"Process temperature {process_temp_c:.0f}°C is outside the 80–200 °C window — heat pump not viable."],
            "assumptions": {}
        }

    # 2) Energy vector & target temperature/pressure
    e = str(energy_vector).lower()

    if e == "steam":
        if steam_pressure_barA is None:
            return {
                "status": "caution",
                "notes": ["Provide steam pressure (barA) to check heat-pump feasibility."],
                "assumptions": {}
            }
        if steam_pressure_barA > TH["steam_pressure_max"]:
            return {
                "status": "not_viable",
                "notes": [f"Steam pressure {steam_pressure_barA:.1f} barA > {TH['steam_pressure_max']} barA — heat pump not possible."],
                "assumptions": {}
            }

    elif e == "hot air":
        if target_supply_temp_c > TH["hp_target_max"]:
            return {
                "status": "not_viable",
                "notes": [f"Required hot-air temperature {target_supply_temp_c:.0f}°C > {TH['hp_target_max']}°C — heat pump not possible."],
                "assumptions": {}
            }
        if target_supply_temp_c > TH["hot_air_caution_max"]:
            return {
                "status": "not_viable",
                "notes": ["Hot air >150 °C — heat pump not recommended (consider heat exchangers)."],
                "assumptions": {}
            }
        if TH["hot_air_ok_max"] < target_supply_temp_c <= TH["hot_air_caution_max"]:
            notes.append("Hot air 110–150 °C — feasible but COP may be modest (high lift).")

    elif e == "hot water":
        if target_supply_temp_c > TH["hp_target_max"]:
            return {
                "status": "not_viable",
                "notes": [f"Required hot-water temperature {target_supply_temp_c:.0f}°C > {TH['hp_target_max']}°C — heat pump not possible."],
                "assumptions": {}
            }

    else:
        notes.append("Unknown energy vector — assuming heat pump can meet the target with reduced COP.")

    # 3) Waste heat yes/no
    if not has_waste_heat:
        return {
            "status": "suggest_hx",
            "notes": ["No waste heat identified — this may be better suited to direct heat recovery via heat exchangers."],
            "assumptions": {}
        }

    # 4) How is waste heat released?
    if how_released == "General ventilation in the production area":
        return {
            "status": "not_viable",
            "notes": [
                "Waste heat only available via general room ventilation — better suited to heat recovery through heat exchangers than a heat pump."
            ],
            "assumptions": {}
        }
    elif how_released == "Dedicated cooling system or exhaust pipe":
        notes.append("Waste heat from a dedicated cooling system or exhaust — suitable for heat-pump integration.")
    elif how_released:
        notes.append(f"Waste heat release path: {how_released} (assumed suitable for a heat pump).")

    # 5) Waste-heat temperature
    if waste_temp_known and (waste_temp_c is not None):
        assumptions["T_in1"] = float(waste_temp_c)
    else:
        assumptions["T_in1"] = float(process_temp_c)
        notes.append("Waste-heat temperature unknown — assuming equal to process temperature.")

    # 6) How much waste heat?
    if waste_amount_known and q_waste_kw is not None and q_waste_kw > 0:
        assumptions["Q_waste_kW"] = float(q_waste_kw)
        notes.append(f"Using user-provided waste heat level Q_waste ≈ {q_waste_kw:.0f} kW.")
    else:
        band = waste_amount_pct_band or "31–50% of energy input"
        band_clean = band.split("of")[0].strip()
        hi_str = band_clean.split("–")[1]
        hi = int("".join(ch for ch in hi_str if ch.isdigit()))
        assumptions["waste_pct"] = hi
        notes.append(f"Waste-heat amount unknown — using upper estimate ≈ {hi}% of energy input.")

    # 7) Waste-heat medium form
    if waste_form:
        assumptions["waste_form"] = waste_form
        if waste_form == "Humid air":
            if humidity_ratio_known == "Yes":
                notes.append("Waste heat available as humid air with known humidity ratio — heat pump integration possible, "
                             "with final sizing refined at design stage.")
            else:
                notes.append("Waste heat available as humid air but humidity ratio unknown — using typical values, "
                             "to be refined during a detailed study.")
        elif waste_form == "Dry hot air":
            notes.append("Waste heat available as dry hot air — suitable for heat pump via an air-to-refrigerant heat exchanger.")
        elif waste_form == "Hot water":
            notes.append("Waste heat available as hot water — highly suitable for heat-pump integration.")
        elif waste_form == "Pure steam":
            notes.append("Waste heat available as pure steam — heat pump integration possible with suitable condenser design.")

    # 8) Existing capture & processor flags
    if waste_heat_captured == "Yes":
        notes.append("Waste heat is already captured — integration may be simpler and cheaper.")
    elif waste_heat_captured == "No":
        notes.append("Waste heat not yet captured — additional pipework/ducting or a heat exchanger may be needed.")

    if has_waste_heat_processor == "Yes":
        notes.append("There is already a waste-heat processing system on site (e.g. ORC or heat-recovery unit).")
    elif has_waste_heat_processor == "No":
        notes.append("No existing waste-heat processor — Mechapres could be the main technology to use that heat.")

    return {
        "status": "proceed" if not notes else "caution",
        "notes": notes,
        "assumptions": assumptions
    }

# ----------------- Simple HP model (technical, background) -----------------
def excel_performance_logic(
    T_in1, T_out2, P_out2, Q_process,
    T_app_condenser=8.0, T_app_evaporator=8.0,
    T_ev_minimum=70.0, lorentz_eff=0.60,
    waste_heat_min_pct=30.0, waste_heat_max_pct=60.0
):
    # These formulas follow the structure of the Simple HP model sheet.
    T_cond_steam = T_out2 + T_app_condenser - 2.0
    T_evap_raw   = T_in1 - T_app_evaporator
    T_evap       = max(T_evap_raw, T_ev_minimum)

    if T_cond_steam <= T_evap:
        COP_carnot = 0.0
    else:
        TcK, TeK = T_cond_steam + 273.15, T_evap + 273.15
        COP_carnot = TcK / (TcK - TeK)

    COP_real = max(0.0, lorentz_eff * COP_carnot)

    wh_min = Q_process * (waste_heat_min_pct/100.0)
    wh_max = Q_process * (waste_heat_max_pct/100.0)

    E_full = (Q_process / COP_real) if COP_real > 0 else float("inf")
    E_min  = E_full/2.0 if math.isfinite(E_full) else float("inf")

    Q2_min = wh_min  # indicative: useful high-grade heat from waste (low case)
    Q2_max = wh_max  # high case

    capacity_MWth = Q_process / 1000.0
    return {
        "T_cond_steam":   T_cond_steam,
        "T_evap":         T_evap,
        "COP_carnot":     COP_carnot,
        "COP_real":       COP_real,
        "waste_heat_min_kW": wh_min,
        "waste_heat_max_kW": wh_max,
        "E_min_kW":       E_min,
        "E_max_kW":       E_full,
        "Q2_min_kW":      Q2_min,
        "Q2_max_kW":      Q2_max,
        "capacity_MWth":  capacity_MWth
    }

# ----------------- PDF generation (uses high case metrics) -----------------
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

def generate_report(inputs, results, logo_path=LOGO_PATH, brand=MECHAPRES_COLORS):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header
    c.setFillColor(colors.HexColor("#ffffff"))
    c.rect(0, height-100, width, 100, stroke=0, fill=1)
    if logo_path:
        try:
            c.drawImage(logo_path, 40, height-85, width=100, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    c.setFillColor(colors.HexColor(brand["primary"]))
    c.setFont("Helvetica-Bold", 15)
    c.drawString(160, height-60, "Industrial Heat Pump Estimation Report")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(160, height-78, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    c.setStrokeColor(colors.HexColor(brand["primary"]))
    c.line(40, height-100, width-40, height-100)

    # Contact
    y = height-125
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Contact Details")
    y -= 16
    c.setFont("Helvetica", 9)
    for label, key in [("Name","contact_name"),("Company","contact_company"),
                       ("Email","contact_email"),("Phone","contact_phone")]:
        val = inputs.get(key)
        if val:
            c.drawString(60, y, f"{label}: {val}")
            y -= 12
    consent_txt = "Yes" if inputs.get("contact_consent") else "No"
    c.drawString(60, y, f"Consent to contact: {consent_txt}")
    y -= 14
    c.setStrokeColor(colors.HexColor(brand["muted"]))
    c.line(40, y, width-40, y)
    y -= 14

    # Inputs
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor(brand["primary"]))
    c.drawString(40, y, "1) Input Summary")
    c.setFillColor(colors.black)
    y -= 16
    c.setFont("Helvetica", 9)
    for key, val in inputs.items():
        if str(key).startswith("contact_"):
            continue
        c.drawString(60, y, f"{key.replace('_',' ').title()}: {val}")
        y -= 12
        if y < 150:
            c.showPage()
            y = height-60

    # Results
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor(brand["primary"]))
    c.drawString(40, y, "2) Results Summary (High case)")
    c.setFillColor(colors.black)
    y -= 16
    c.setFont("Helvetica", 9)
    summary_lines = [
        ("System Thermal Capacity (MWth)", f"{results.get('capacity_MWth',0):.2f}"),
        ("Estimated COP",                  f"{results.get('cop',0):.2f}"),
        ("Annual Useful Heat (MWh)",       f"{results.get('Q_steam_MWh',0):.0f}"),
        ("Annual Cost Savings (high case, £)", f"{results.get('savings_high',0):,.0f}"),
        ("CO₂ Reduction (t/year)",         f"{results.get('co2_savings',0):,.0f}"),
        ("Simple Payback (high case, years)", f"{results.get('payback_high',0):.1f}"),
        ("IRR high case (10 years)",       f"{results.get('irr_high',0):.0f}%"),
    ]
    for k, v in summary_lines:
        c.drawString(60, y, f"{k}: {v}")
        y -= 12

    # Charts (cost & CO2)
    y -= 6
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor(brand["primary"]))
    c.drawString(40, y, "3) Cost & Emission Comparison")
    c.setFillColor(colors.black)
    y -= 120

    systems = ['Current', 'Mechapres']
    cost_vals = [results.get('cost_current',0), results.get('cost_mechapres',0)]
    co2_vals  = [results.get('co2_current',0),  results.get('co2_mechapres',0)]

    fig1, ax1 = plt.subplots(figsize=(3.6,2.2))
    fig1.patch.set_alpha(0.0); ax1.set_facecolor('none')
    ax1.bar(systems, cost_vals, color=["#9CA3AF", MECHAPRES_COLORS["accent"]])
    ax1.set_title("Annual Energy Cost (£)"); ax1.set_ylabel("£/year")
    fig1.tight_layout()
    img1 = BytesIO()
    fig1.savefig(img1, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig1); img1.seek(0)

    fig2, ax2 = plt.subplots(figsize=(3.6,2.2))
    fig2.patch.set_alpha(0.0); ax2.set_facecolor('none')
    ax2.bar(systems, co2_vals, color=["#9CA3AF", MECHAPRES_COLORS["accent"]])
    ax2.set_title("Annual CO₂ Emissions (t/yr)"); ax2.set_ylabel("tCO₂/yr")
    fig2.tight_layout()
    img2 = BytesIO()
    fig2.savefig(img2, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig2); img2.seek(0)

    c.drawImage(ImageReader(img1), 50,  y, width=220, height=110, mask='auto')
    c.drawImage(ImageReader(img2), 310, y, width=220, height=110, mask='auto')

    # Notes
    y -= 120
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor(brand["primary"]))
    c.drawString(40, y, "4) Viability Notes")
    c.setFillColor(colors.black)
    y -= 14
    c.setFont("Helvetica", 9)
    for msg in results.get("messages", []):
        c.drawString(60, y, f"- {msg}")
        y -= 12
        if y < 80:
            c.showPage()
            y = height-60

    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.HexColor(MECHAPRES_COLORS["muted"]))
    c.drawString(40, y, "Disclaimer: Indicative estimates only. For detailed feasibility, contact info@mechapres.co.uk.")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ----------------- Email utility -----------------
import smtplib, ssl
from email.message import EmailMessage
from email.utils import formatdate

def send_email_with_pdf(subject, body, to_addr, pdf_bytes, pdf_filename):
    try:
        host = st.secrets["SMTP_HOST"]; port = int(st.secrets["SMTP_PORT"])
        user = st.secrets["SMTP_USER"]; pwd  = st.secrets["SMTP_PASS"]
    except Exception:
        raise RuntimeError("SMTP secrets missing. Add them in .streamlit/secrets.toml")
    msg = EmailMessage()
    msg["From"] = user
    msg["To"]   = to_addr
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename)
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, pwd)
        server.send_message(msg)

# ----------------- Streamlit layout -----------------
st.set_page_config(page_title="Mechapres Industrial Heat Pump Calculator", layout="wide")
apply_brand_theme()
show_brand_bar()
tabs = st.tabs(["🏠 Welcome", "1️⃣ Project", "2️⃣ Economics", "✅ Results"])

# ===== Tab 0: Welcome =====
with tabs[0]:
    st.title("Mechapres Industrial Heat Pump Estimator")

    st.markdown(
        """
        ### Welcome to Mechapres high-temperature heat pumps

        Mechapres combines **high-temperature heat pumps** with **thermal storage** to turn low-grade
        heat (waste heat, solar, off-peak electricity) into the **steam and hot water your process needs**.

        With this quick calculator you can:
        - Check whether a heat pump is suitable for your process.
        - Estimate potential **energy cost savings** and **CO₂ cuts**.
        - Explore a **conservative (low)** and **ambitious (high)** project size.

        """
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### 💸 Cut operating costs\nUse low-cost electricity and waste heat instead of fossil fuel.")
    with c2:
        st.markdown("#### 🌍 Decarbonise steam\nReduce CO₂ emissions from your existing boiler plant.")
    with c3:
        st.markdown("#### 🧩 Easy integration\nModular skid that ties into your existing process utilities.")

    st.markdown("---")

    if st.button("🚀 Get a quote", key="welcome_quote", use_container_width=True):
        st.session_state.welcome_hint = (
            "Great – now move to **1️⃣ Project** at the top, then **2️⃣ Economics** and finally **✅ Results** "
            "to see your tailored Mechapres estimate."
        )

    if st.session_state.welcome_hint:
        st.success(st.session_state.welcome_hint)

    st.info("You can move between the tabs at the top at any time. Your answers are remembered automatically.")

# ===== Tab 1: Project =====
with tabs[1]:
    st.title("Step 1 — Project")
    st.markdown("Answer a few quick questions. We’ll check feasibility and set sensible assumptions for your site.")

    st.markdown("### Your goals")
    ambitions = st.multiselect(
        "My reasons to act…",
        ["Reduce energy cost","Increase comfort","Need renovation","Compliance","Improve competitiveness","CSR goals"],
        default=st.session_state.get("ambitions",["Reduce energy cost","CSR goals"])
    )
    st.session_state["ambitions"] = ambitions

    st.markdown("### Basic site parameters")
    colA, colB = st.columns(2)
    process_temp = colA.number_input(
        "Process temperature (°C)",
        20.0, 300.0,
        st.session_state.get("process_temp",150.0),
        key="process_temp",
        help="Typical operating temperature of your industrial process that needs heat."
    )
    energy_vector = colB.selectbox(
        "Energy vector used to provide heat",
        ["Steam","Hot Water","Hot Air"],
        key="energy_vector",
        help="The main medium currently used to supply heat to your process."
    )

    heat_supply_tech = st.selectbox(
        "How are you providing heat to the process?",
        ["Fossil fuel boiler", "Electric boiler", "Industrial heat pump", "Combined heat and power", "Other"],
        key="heat_supply_tech",
        help="Select the main technology currently providing heat to this process."
    )

    colC, colD = st.columns(2)
    T_out2 = colC.number_input(
        "Required supply temperature (°C)",
        50.0, 250.0,
        st.session_state.get("T_out2",150.0),
        key="T_out2"
    )
    steam_p = None
    if st.session_state.energy_vector == "Steam":
        steam_p = colD.number_input(
            "Steam supply pressure (barA)",
            1.0, 20.0,
            st.session_state.get("steam_p",5.0),
            key="steam_p",
            help="Operating pressure of your steam line in bar absolute."
        )

    colD1, colD2 = st.columns(2)
    prod_days = colD1.number_input(
        "Days of production per year",
        1, 365,
        st.session_state.get("prod_days", 250),
        key="prod_days",
        help="How many days in a typical year your process is running (not necessarily 365)."
    )
    prod_hours_day = colD2.number_input(
        "Hours of production per day",
        1, 24,
        st.session_state.get("prod_hours_per_day", 12),
        key="prod_hours_per_day",
        help="Average number of hours per production day that the process is running."
    )

    operating_hours_est = float(prod_days) * float(prod_hours_day)
    st.markdown(f"**Implied operating hours per year:** `{operating_hours_est:.0f} h/year`")

    colE1, colE2 = st.columns(2)
    waste_heat_captured = colE1.radio(
        "Is the waste heat captured from the current process?",
        ["Yes","No"],
        index=0 if st.session_state.get("waste_heat_captured","No") == "Yes" else 1,
        key="waste_heat_captured",
        help="Waste heat is 'captured' if it is already collected in ducting/pipework or a heat recovery system rather than being vented."
    )
    has_waste_heat_processor = colE2.radio(
        "Do you have a waste heat processor?",
        ["Yes","No"],
        index=0 if st.session_state.get("has_waste_heat_processor","No") == "Yes" else 1,
        key="has_waste_heat_processor",
        help="Select **Yes** if you already have equipment that uses waste heat (e.g. a heat recovery unit or ORC)."
    )

    st.markdown("### Waste heat")
    has_waste = st.radio(
        "Do you have waste heat from current processes?",
        ["Yes","No"],
        index=0 if st.session_state.get("has_waste","Yes") == "Yes" else 1,
        key="has_waste",
        help="Waste heat = heat that is currently rejected to air, water, or a cooling system and is not fully used in your process."
    )

    colR1, colR2 = st.columns(2)
    how_released = colR1.radio(
        "How is the waste heat released?",
        ["Dedicated cooling system or exhaust pipe",
         "General ventilation in the production area",
         "Other / Not sure"],
        index=0,
        key="how_released",
        help="If it mainly escapes via general room ventilation, a direct heat-recovery solution may be more suitable than a heat pump."
    )

    colE, colF = st.columns(2)
    w_temp_known = colE.radio(
        "Is the waste-heat temperature known?",
        ["Yes","No"],
        index=0 if st.session_state.get("w_temp_known","Yes") == "Yes" else 1,
        key="w_temp_known",
        help="**Yes** if you have measurements or design data (e.g. exhaust at 120°C). **No** if you only have a rough idea."
    )
    w_temp = None
    if st.session_state.w_temp_known == "Yes":
        w_temp = colF.number_input(
            "Waste-heat temperature (°C)",
            0.0, 250.0,
            st.session_state.get("w_temp", 100.0),
            key="w_temp"
        )

    colG, colH = st.columns(2)
    w_amt_known = colG.radio(
        "Do you know how much heat is released as waste?",
        ["Yes","No"],
        index=1 if st.session_state.get("w_amt_known","No") == "No" else 0,
        key="w_amt_known",
        help="**Yes** if you know the thermal power or flow rate of the waste stream. **No** if you prefer a percentage estimate."
    )

    q_waste_kw = None
    if st.session_state.w_amt_known == "Yes":
        q_waste_kw = colH.number_input(
            "Waste heat available (kW)",
            0.0, 100000.0,
            st.session_state.get("q_waste_kw", 1000.0),
            key="q_waste_kw",
            help="Numerical input Q_waste, used to refine the economic calculation."
        )
        w_amt_band = None
    else:
        w_amt_band = colH.selectbox(
            "Estimate waste heat fraction",
            ["10–30% of energy input",
             "31–50% of energy input",
             "51–80% of energy input"],
            index=1,
            key="w_amt_band",
            help="Estimate what fraction of your total energy input is ultimately rejected as waste heat."
        )

    st.markdown("#### Waste-heat medium")
    default_form = "Hot water"
    if energy_vector == "Steam":
        default_form = "Pure steam"
    elif energy_vector == "Hot Water":
        default_form = "Hot water"
    elif energy_vector == "Hot Air":
        default_form = "Dry hot air"

    waste_form = st.selectbox(
        "In which form is waste heat available?",
        ["Humid air","Dry hot air","Hot water","Pure steam","Don't know"],
        index=["Humid air","Dry hot air","Hot water","Pure steam","Don't know"].index(default_form),
        key="waste_form",
        help="This helps to characterise the heat-pump connection (air, water, steam)."
    )

    humidity_ratio_known = None
    if waste_form == "Humid air":
        humidity_ratio_known = st.radio(
            "Is the humidity ratio of the air known?",
            ["Yes","No"],
            index=1,
            key="humidity_ratio_known",
            help="If unknown, typical values will be assumed and refined during a detailed study."
        )

    gate = evaluate_decision_tree(
        process_temp_c=st.session_state.process_temp,
        energy_vector=st.session_state.energy_vector,
        target_supply_temp_c=st.session_state.T_out2,
        steam_pressure_barA=steam_p,
        has_waste_heat=(st.session_state.has_waste == "Yes"),
        waste_temp_known=(st.session_state.w_temp_known == "Yes"),
        waste_temp_c=w_temp,
        waste_amount_known=(st.session_state.w_amt_known == "Yes"),
        waste_amount_pct_band=w_amt_band,
        waste_heat_captured=st.session_state.get("waste_heat_captured"),
        has_waste_heat_processor=st.session_state.get("has_waste_heat_processor"),
        how_released=how_released,
        waste_form=waste_form if waste_form != "Don't know" else None,
        humidity_ratio_known=humidity_ratio_known,
        q_waste_kw=q_waste_kw
    )
    st.session_state._gate = gate

    if gate["status"] == "not_viable":
        st.error("Not viable for a heat pump with the current inputs (see notes below).")
    elif gate["status"] == "suggest_hx":
        st.warning("This case looks better suited to a heat-exchanger project than a heat pump.")
    elif gate["status"] == "caution":
        st.info("Feasible with caveats (see notes below).")
    for n in gate["notes"]:
        st.write(f"- {n}")

# ===== Tab 2: Economics =====
with tabs[2]:
    st.title("Step 2 — Economics")
    gate = st.session_state.get("_gate", {"assumptions": {}})

    if gate.get("status") == "not_viable":
        st.warning("The screening indicates this case is **not viable for a heat pump**. "
                   "You can still explore indicative economics, but results should be treated with caution.")

    st.markdown("### Demand & energy prices")

    # Operating hours (from Step 1 by default)
    default_hours = float(st.session_state.get("prod_days", 250)) * float(st.session_state.get("prod_hours_per_day", 12))
    default_hours = max(100.0, min(default_hours, 8760.0))

    e0, e1 = st.columns(2)
    operating_hours  = e0.number_input(
        "Operating hours per year",
        100.0, 8760.0,
        default_hours,
        help="Pre-filled from your inputs: days of production × hours per day. You can adjust if needed."
    )

    yearly_cost = e1.number_input(
        "Approx. annual energy spend for this process ( £/year )",
        0.0, 1_000_000_000.0,
        500_000.0,
        help="Cost of fuel or electricity currently used to run this process (not the whole site)."
    )

    # Fuel type selection with embedded emission factors
    e2, e3 = st.columns(2)
    default_fuel = st.session_state.get("fuel_type", "Natural gas")
    if default_fuel not in FUEL_OPTIONS:
        default_fuel = "Natural gas"
    fuel_type = e2.selectbox(
        "Fuel type used by the current system",
        FUEL_OPTIONS,
        index=FUEL_OPTIONS.index(default_fuel),
        help="Emission factors are based on kgCO₂ per kWh (Net CV) for the selected fuel."
    )
    st.session_state["fuel_type"] = fuel_type

    # Prices are in £/MWh – easier for industrial users
    fuel_price = e3.number_input(
        "Fuel cost ( £/MWh )",
        0.0, 300.0, 30.0,
        help="Average cost of the fuel used by your current system."
    )

    e4, e5 = st.columns(2)
    electricity_price = e4.number_input(
        "Electricity cost ( £/MWh )",
        0.0, 300.0, 90.0,
        help="Electricity tariff that would be used to power the heat pump."
    )
    boiler_eff_pct = e5.number_input(
        "Existing system efficiency (%)",
        40.0, 100.0,
        80.0 if st.session_state.get("heat_supply_tech","Fossil fuel boiler") == "Fossil fuel boiler" else 95.0,
        help="Use ~80% for fossil boilers, ~95% for electric boilers/HP."
    )
    boiler_eff = boiler_eff_pct / 100.0

    st.markdown("#### Annual energy costs (scale of site)")
    band_options = ["<£100k","£100k–£500k",">£500k"]
    annual_band = st.radio(
        "Approximate annual energy spend category",
        band_options,
        index=band_options.index(st.session_state.get("annual_band","£100k–£500k")),
        horizontal=True,
        key="annual_band"
    )

    # CO2 factors in the background
    emission_factor_fuel_kWh = FUEL_EMISSION_FACTORS_KG_PER_KWH[fuel_type]
    emission_factor_fuel_MWh = emission_factor_fuel_kWh * 1000.0
    emission_factor_elec = ELECTRICITY_CO2_KG_PER_MWH
    st.caption(
        f"Using **{emission_factor_fuel_kWh:.3f} kgCO₂/kWh** (Net CV) for {fuel_type} "
        f"and **{emission_factor_elec:.0f} kgCO₂/MWh** for electricity (applied in the background)."
    )

    # --------- Derive Q_process from annual cost (Excel-style) ---------
    unit_cost_baseline = fuel_price if fuel_price > 0 else max(electricity_price, 1.0)

    Q_process_guess = 100.0
    if unit_cost_baseline > 0 and operating_hours > 0:
        energy_purchased_MWh = yearly_cost / unit_cost_baseline
        useful_MWh = energy_purchased_MWh * boiler_eff
        Q_process_guess = max(10.0, useful_MWh * 1000.0 / operating_hours)

    Q_process = st.number_input(
        "Estimated average process heat demand (kW)",
        10.0, 50000.0,
        float(Q_process_guess),
        help="Calculated from your annual energy spend and efficiency. You can adjust if needed."
    )

    # --------- Technical performance (Simple HP model) ---------
    gate = st.session_state.get("_gate", {"assumptions": {}})
    T_in1 = gate["assumptions"].get(
        "T_in1",
        st.session_state.get("w_temp", st.session_state.get("process_temp", 120.0))
    )
    T_out2 = st.session_state.get("T_out2", 150.0)
    P_out2 = 5.0
    T_app_condenser = 8.0
    T_app_evap      = 8.0
    T_ev_minimum    = 70.0
    lorentz_eff     = 0.60

    waste_pct_assumed = gate["assumptions"].get("waste_pct", 40)
    waste_min_pct = max(10, min(90, waste_pct_assumed - 10))
    waste_max_pct = max(waste_min_pct + 5, min(100, waste_pct_assumed + 10))

    perf = excel_performance_logic(
        T_in1=T_in1, T_out2=T_out2, P_out2=P_out2, Q_process=Q_process,
        T_app_condenser=T_app_condenser, T_app_evaporator=T_app_evap,
        T_ev_minimum=T_ev_minimum, lorentz_eff=lorentz_eff,
        waste_heat_min_pct=waste_min_pct, waste_heat_max_pct=waste_max_pct
    )

    if perf["COP_real"] <= 0 or not math.isfinite(perf["E_max_kW"]):
        st.error("❌ Estimated COP not feasible with the current temperature assumptions. "
                 "Please review Step 1 (supply & waste-heat temperatures).")
    else:
        # --------- Baseline vs Mechapres energy & CO2 ---------
        Q_steam_MWh = (Q_process * operating_hours) / 1000.0
        COP_mechapres = perf["COP_real"]
        E_hp_electric_MWh = Q_steam_MWh / COP_mechapres

        # baseline input energy: Q / efficiency
        E_current_MWh = Q_steam_MWh / boiler_eff

        cost_current = E_current_MWh * fuel_price
        co2_current  = E_current_MWh * emission_factor_fuel_MWh / 1000.0  # tonnes

        cost_mechapres = E_hp_electric_MWh * electricity_price
        co2_mechapres  = E_hp_electric_MWh * emission_factor_elec / 1000.0

        annual_savings_high = cost_current - cost_mechapres
        co2_savings = co2_current - co2_mechapres

        # --------- Investment variables and Low/High cases (Economic calculations sheet) ---------
        st.markdown("### Investment variables")
        inv1, inv2 = st.columns(2)
        design_pm = inv1.number_input(
            "Design and project management (£)",
            0.0, 10_000_000.0,
            50_000.0,
            help="Indicative allowance for design and project management."
        )
        fixed_install = inv2.number_input(
            "Fixed installation costs (£)",
            0.0, 10_000_000.0,
            50_000.0,
            help="Base installation costs that do not scale with heat-pump size."
        )

        inv3, inv4, inv5 = st.columns(3)
        hp_cost_per_kw = inv3.number_input(
            "Heat pump cost ( £/kW )",
            0.0, 5_000.0, 250.0
        )
        hr_cost_per_kw = inv4.number_input(
            "Heat recovery system cost ( £/kW )",
            0.0, 5_000.0, 50.0
        )
        var_install_per_kw = inv5.number_input(
            "Variable installation costs ( £/kW )",
            0.0, 5_000.0, 10.0
        )

        # HP sizes – High case uses full process load; Low case ~ half
        hp_size_high_kw = max(250.0, perf["capacity_MWth"] * 1000.0)
        hp_size_low_kw  = max(250.0, hp_size_high_kw / 2.0)
        hr_size_high_kw = 0.66 * hp_size_high_kw
        hr_size_low_kw  = 0.66 * hp_size_low_kw

        def total_investment(hp_kw, hr_kw):
            variable_cost = hp_kw*hp_cost_per_kw + hr_kw*hr_cost_per_kw + (hp_kw+hr_kw)*var_install_per_kw
            return design_pm + fixed_install + variable_cost

        capex_low  = total_investment(hp_size_low_kw,  hr_size_low_kw)
        capex_high = total_investment(hp_size_high_kw, hr_size_high_kw)

        # Savings: high case full; low case ~ 15% of high (based on Excel example)
        savings_high = max(annual_savings_high, 0.0)
        savings_low  = max(0.15 * savings_high, 0.0)

        def simple_payback(capex, savings):
            return capex / savings if savings > 0 else float("inf")

        def irr_from_savings(capex, savings, years=10):
            if savings <= 0:
                return 0.0
            low_r, high_r = 0.0, 1.0
            for _ in range(60):
                r = (low_r + high_r) / 2
                npv = -capex
                for t in range(1, years+1):
                    npv += savings / ((1 + r) ** t)
                if npv > 0:
                    low_r = r
                else:
                    high_r = r
            return (low_r + high_r) / 2 * 100.0  # %

        payback_low  = simple_payback(capex_low,  savings_low)
        payback_high = simple_payback(capex_high, savings_high)
        irr_low  = irr_from_savings(capex_low,  savings_low,  years=10)
        irr_high = irr_from_savings(capex_high, savings_high, years=10)

        st.subheader("💰 Savings range")
        s1, s2 = st.columns(2)
        s1.metric("Annual savings — low case",  f"£{savings_low:,.0f}",  help="Conservative case with smaller heat-pump size.")
        s2.metric("Annual savings — high case", f"£{savings_high:,.0f}", help="Larger heat-pump project capturing more savings.")

        st.subheader("📦 Investment and returns")
        colL, colH = st.columns(2)

        with colL:
            st.markdown("**Low case** (smaller project)")
            st.write(f"Heat pump size: **{hp_size_low_kw:,.0f} kW**")
            st.write(f"Heat recovery size: **{hr_size_low_kw:,.0f} kW**")
            st.write(f"Total investment cost: **£{capex_low:,.0f}**")
            st.write(f"Simple payback: **{payback_low:.1f} years**" if math.isfinite(payback_low) else "Simple payback: n/a")
            st.write(f"IRR (10 years): **{irr_low:.0f}%**")

        with colH:
            st.markdown("**High case** (larger project)")
            st.write(f"Heat pump size: **{hp_size_high_kw:,.0f} kW**")
            st.write(f"Heat recovery size: **{hr_size_high_kw:,.0f} kW**")
            st.write(f"Total investment cost: **£{capex_high:,.0f}**")
            st.write(f"Simple payback: **{payback_high:.1f} years**" if math.isfinite(payback_high) else "Simple payback: n/a")
            st.write(f"IRR (10 years): **{irr_high:.0f}%**")

        st.caption("Note: For projects below ~250 kW, alternative solutions may be more suitable. The calculator enforces a minimum indicative size of 250 kW.")

        # Store info for Results & PDF
        st.session_state._perf_inputs = {
            "T_in1": T_in1, "T_out2": T_out2,
            "T_in2": max(T_out2 - 20.0, 20.0),
            "P_out2": P_out2,
            "Q_process": Q_process,
            "T_app_cond": T_app_condenser, "T_app_evap": T_app_evap,
            "T_ev_minimum": T_ev_minimum, "lorentz_eff": lorentz_eff,
            "waste_min_pct": waste_min_pct, "waste_max_pct": waste_max_pct
        }
        st.session_state._perf = perf
        st.session_state._econ = {
            "operating_hours":operating_hours,
            "yearly_cost":yearly_cost,
            "fuel_price":fuel_price,
            "electricity_price":electricity_price,
            "boiler_eff":boiler_eff,
            "emission_factor_fuel_kWh": emission_factor_fuel_kWh,
            "emission_factor_fuel_MWh": emission_factor_fuel_MWh,
            "emission_factor_elec":emission_factor_elec,
            "Q_steam_MWh":Q_steam_MWh,
            "E_current_MWh":E_current_MWh,
            "E_hp_electric_MWh":E_hp_electric_MWh,
            "cost_current":cost_current,
            "cost_mechapres":cost_mechapres,
            "annual_savings_high":savings_high,
            "annual_savings_low":savings_low,
            "co2_current":co2_current,
            "co2_mechapres":co2_mechapres,
            "co2_savings":co2_savings,
            "hp_size_low_kw":hp_size_low_kw,
            "hp_size_high_kw":hp_size_high_kw,
            "hr_size_low_kw":hr_size_low_kw,
            "hr_size_high_kw":hr_size_high_kw,
            "capex_low":capex_low,
            "capex_high":capex_high,
            "payback_low":payback_low,
            "payback_high":payback_high,
            "irr_low":irr_low,
            "irr_high":irr_high,
            "annual_band": annual_band,
            "heat_supply_tech": st.session_state.get("heat_supply_tech","Fossil fuel boiler"),
            "fuel_type": fuel_type
        }

# ===== Tab 3: Results =====
with tabs[3]:
    st.title("Results — Your Estimate")
    perf = st.session_state.get("_perf")
    perf_inputs = st.session_state.get("_perf_inputs", {})
    econ = st.session_state.get("_econ", {})

    if not (perf and perf_inputs and econ):
        st.warning("Complete Steps **1–2** to see results here.")
    else:
        c = st.columns(3)
        c[0].metric("Estimated COP", f"{perf['COP_real']:.2f}")
        c[1].metric("Annual savings (high case)", f"£{econ['annual_savings_high']:,.0f}")
        c[2].metric("Simple payback (high case)", f"{econ['payback_high']:.1f} years" if math.isfinite(econ['payback_high']) else "n/a")

        with st.expander("Low vs high case comparison", expanded=False):
            st.write(f"**Low case** — savings £{econ['annual_savings_low']:,.0f}/year, "
                     f"payback {econ['payback_low']:.1f} years, IRR {econ['irr_low']:.0f}%")
            st.write(f"**High case** — savings £{econ['annual_savings_high']:,.0f}/year, "
                     f"payback {econ['payback_high']:.1f} years, IRR {econ['irr_high']:.0f}%")

        st.header("📇 Contact Details")
        if st.session_state.show_contact:
            with st.form("contact_form"):
                colA, colB = st.columns(2)
                name = colA.text_input("Full Name")
                company = colB.text_input("Company")
                email = colA.text_input("Work Email")
                phone = colB.text_input("Phone (optional)")
                consent = st.checkbox("I agree to be contacted by Mechapres regarding this estimate.")
                submitted = st.form_submit_button("Save Contact Info")
                if submitted:
                    if not (name and email and consent):
                        st.warning("Please provide your name, email, and consent.")
                    else:
                        st.success("Contact details saved for PDF/email.")
                        st.session_state.contact_name = name
                        st.session_state.contact_company = company
                        st.session_state.contact_email = email
                        st.session_state.contact_phone = phone
                        st.session_state.contact_consent = consent
                        st.session_state.show_contact = False
        else:
            if st.button("Open Contact Form", key="cta_inline"):
                st.session_state.show_contact = True
            name = st.session_state.get("contact_name","")
            company = st.session_state.get("contact_company","")
            email = st.session_state.get("contact_email","")
            phone = st.session_state.get("contact_phone","")
            consent = st.session_state.get("contact_consent",False)

        gate = st.session_state.get("_gate", {"notes":[]})
        inputs_for_pdf = {
            "Process_temperature_C":      st.session_state.get("process_temp"),
            "Energy_vector":              st.session_state.get("energy_vector"),
            "Heat_supply_technology":     econ.get("heat_supply_tech"),
            "Fuel_type":                  econ.get("fuel_type"),
            "Days_production_per_year":   st.session_state.get("prod_days"),
            "Hours_production_per_day":   st.session_state.get("prod_hours_per_day"),
            "T_in1":                      perf_inputs.get("T_in1"),
            "T_out2":                     perf_inputs.get("T_out2"),
            "T_in2":                      perf_inputs.get("T_in2"),
            "P_out2":                     perf_inputs.get("P_out2"),
            "Q_process_kW":               perf_inputs.get("Q_process"),
            "T_app_condenser_K":          perf_inputs.get("T_app_cond"),
            "T_app_evaporator_K":         perf_inputs.get("T_app_evap"),
            "T_ev_minimum_C":             perf_inputs.get("T_ev_minimum"),
            "lorentz_eff":                perf_inputs.get("lorentz_eff"),
            "Waste_heat_min_%":           perf_inputs.get("waste_min_pct"),
            "Waste_heat_max_%":           perf_inputs.get("waste_max_pct"),
            "Operating_hours":            econ.get("operating_hours"),
            "Annual_energy_cost_£/yr":    econ.get("yearly_cost"),
            "Fuel_price_£/MWh":           econ.get("fuel_price"),
            "Electricity_price_£/MWh":    econ.get("electricity_price"),
            "Boiler_efficiency":          econ.get("boiler_eff"),
            "Annual_energy_band":         econ.get("annual_band"),
            "EF_fuel_kgCO2_per_kWh":      econ.get("emission_factor_fuel_kWh"),
            "EF_elec_kgCO2_per_MWh":      econ.get("emission_factor_elec"),
            "contact_name":               name,
            "contact_company":            company,
            "contact_email":              email,
            "contact_phone":              phone,
            "contact_consent":            consent
        }
        messages = list(gate.get("notes", [])) + ["Technical performance model applied in the background to estimate COP and savings."]

        results_for_pdf = {
            "capacity_MWth": perf["capacity_MWth"],
            "cop":           perf["COP_real"],
            "Q_steam_MWh":   econ["Q_steam_MWh"],
            "cost_current":  econ["cost_current"],
            "cost_mechapres":econ["cost_mechapres"],
            "savings_high":  econ["annual_savings_high"],
            "co2_current":   econ["co2_current"],
            "co2_mechapres": econ["co2_mechapres"],
            "co2_savings":   econ["co2_savings"],
            "payback_high":  econ["payback_high"],
            "irr_high":      econ["irr_high"],
            "messages":      messages,
        }

        st.markdown("### 📄 Download or Send Your Report")
        pdf_buffer = generate_report(inputs_for_pdf, results_for_pdf, LOGO_PATH, MECHAPRES_COLORS)
        pdf_bytes = pdf_buffer.getvalue()
        fname = f"Mechapres_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        st.download_button("📥 Download PDF Report", data=pdf_bytes, file_name=fname, mime="application/pdf")

        col_send1, col_send2 = st.columns(2)
        if col_send1.button("📧 Email this report to me"):
            if email and consent:
                try:
                    send_email_with_pdf(
                        "Your Mechapres Heat Pump Estimate",
                        f"Hi {name or ''},\n\nAttached is your Mechapres industrial heat pump estimate.\n\nBest regards,\nMechapres",
                        email, pdf_bytes, fname
                    )
                    st.success("Report emailed to your address.")
                except Exception as e:
                    st.error(f"Email failed: {e}")
            else:
                st.warning("Please provide your email and consent in Contact Details (above).")

        if col_send2.button("📨 Send to Mechapres sales"):
            try:
                sales_to = st.secrets.get("SALES_TO", None)
                if not sales_to:
                    raise RuntimeError("Missing SALES_TO in secrets.")
                body = ("New calculator lead.\n\n"
                        f"Name: {name}\nCompany: {company}\nEmail: {email}\nPhone: {phone}\nConsent: {consent}\n\n"
                        "Estimate PDF attached.")
                send_email_with_pdf("New Mechapres Calculator Lead", body, sales_to, pdf_bytes, fname)
                st.success("Report sent to Mechapres sales.")
            except Exception as e:
                st.error(f"Email to sales failed: {e}")

# ===== Global reset button =====
st.divider()
if st.button("🔁 Reset all", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

