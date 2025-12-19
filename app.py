# app.py — Mechapres Industrial Heat Pump Calculator
# Professional multi-page flow for customer estimates
# DEBUGGED VERSION v2.0

import math
from io import BytesIO
from datetime import datetime

import streamlit as st
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt

mpl.rcParams["figure.facecolor"] = "none"
mpl.rcParams["axes.facecolor"] = "none"

MECHAPRES_COLORS = {
    "primary": "#0066cc",      # Vibrant blue
    "secondary": "#004d99",    # Deep blue
    "accent": "#3399ff",       # Sky blue
    "light_blue": "#e6f2ff",   # Light blue
    "text": "#1a1a1a",         # Dark text
    "text_light": "#4d4d4d",   # Grey text
    "muted": "#666666",        # Muted grey
    "white": "#ffffff",        # White
    "background": "#f5f5f5",   # Light gray background
    "border": "#cce5ff",       # Light blue border
    "success": "#00aa66",      # Green
    "warning": "#ff9933",      # Orange
    "error": "#cc3333"         # Red
}
LOGO_PATH = "mechapres_logo.png"

# Fuel emission factors (kg CO2 per kWh, Net CV)
FUEL_EMISSION_FACTORS_KG_PER_KWH = {
    "Butane": 0.24107,
    "LNG": 0.20489,
    "LPG": 0.23032,
    "Natural gas": 0.20270,
    "Propane": 0.23258,
    "Fuel oil": 0.28523,
    "Coal (industrial)": 0.33944,
}
FUEL_OPTIONS = list(FUEL_EMISSION_FACTORS_KG_PER_KWH.keys())

# Electricity CO2 factor (kg CO2 per MWh)
ELECTRICITY_CO2_KG_PER_MWH = 50.0

# Page navigation - Investment Variables hidden from customers
PAGES = [
    "Welcome",
    "Basic Site Parameters",
    "Waste Heat",
    "Investment & Returns"
]

# ==================== SESSION STATE INITIALIZATION ====================

def init_session_state():
    """Initialize all session state variables with defaults"""
    
    # Navigation
    if "current_page" not in st.session_state:
        st.session_state.current_page = 0
    if "show_contact" not in st.session_state:
        st.session_state.show_contact = False
    
    # Basic Site Parameters
    defaults = {
        "process_temp": 150.0,
        "energy_vector": "Steam",
        "heat_supply_tech": "Fossil fuel boiler",
        "T_out2": 150.0,
        "steam_p": 5.0,
        "prod_days": 250,
        "prod_hours_per_day": 12,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Waste Heat
    waste_defaults = {
        "has_waste": "Yes",
        "how_released": "Dedicated cooling system or exhaust pipe",
        "w_temp_known": "Yes",
        "w_temp": 100.0,
        "w_amt_known": "No",
        "q_waste_kw": 1000.0,
        "w_amt_band": "31-50% (average for modern processes)",
        "waste_heat_captured": "No",
        "has_waste_heat_processor": "No",
    }
    
    for key, value in waste_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Waste Heat Medium
    if "waste_form" not in st.session_state:
        st.session_state.waste_form = "Hot water"
    if "humidity_ratio_known" not in st.session_state:
        st.session_state.humidity_ratio_known = "No"
    
    # Demand & Energy Prices
    if "operating_hours" not in st.session_state:
        calculated = float(st.session_state.prod_days) * float(st.session_state.prod_hours_per_day)
        st.session_state.operating_hours = min(max(calculated, 100.0), 8760.0)
    
    energy_defaults = {
        "yearly_cost": 500000.0,
        "fuel_type": "Natural gas",
        "fuel_price": 30.0,
        "electricity_price": 90.0,
        "boiler_eff_pct": 80.0,
    }
    
    for key, value in energy_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Annual Energy Costs
    if "annual_band" not in st.session_state:
        st.session_state.annual_band = "£100k–£500k"
    
    # Investment Variables
    investment_defaults = {
        "design_pm": 50000.0,
        "fixed_install": 50000.0,
        "hp_cost_per_kw": 250.0,
        "hr_cost_per_kw": 50.0,
        "var_install_per_kw": 10.0,
    }
    
    for key, value in investment_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# Call initialization
init_session_state()

# ==================== HELPER FUNCTIONS ====================

def system_uses_fuel(heat_supply_tech):
    """Determine if the heat supply system uses fuel or electricity"""
    electric_systems = ["Electric boiler", "Industrial heat pump"]
    return heat_supply_tech not in electric_systems

def get_efficiency_default(heat_supply_tech):
    """Get default efficiency based on heat supply technology"""
    efficiency_map = {
        "Electric boiler": 95.0,
        "Industrial heat pump": 90.0,
        "Combined heat and power": 90.0,
        "Fossil fuel boiler": 80.0,
        "Other": 80.0
    }
    return efficiency_map.get(heat_supply_tech, 80.0)

def calculate_operating_hours():
    """Calculate operating hours from production days and hours per day"""
    days = float(st.session_state.get("prod_days", 250))
    hours_per_day = float(st.session_state.get("prod_hours_per_day", 12))
    return min(max(days * hours_per_day, 100.0), 8760.0)

# ==================== UI COMPONENTS ====================

def apply_brand_theme():
    """Apply light gray professional theme with identical structure on all devices"""
    css = """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
      
      /* Light gray color theme */
      :root {
        --primary-blue: #0066cc;
        --deep-blue: #004d99;
        --sky-blue: #3399ff;
        --light-gray: #e8e8e8;
        --medium-gray: #d0d0d0;
        --border-gray: #c0c0c0;
        --text-dark: #1a1a1a;
        --text-grey: #4d4d4d;
        --white: #ffffff;
        --background-gray: #f5f5f5;
      }

      /* Base styles - Light gray background */
      html, body, [data-testid="stAppViewContainer"], .stApp {
        font-family: 'Inter', sans-serif;
        color: var(--text-dark);
        background-color: var(--background-gray) !important;
      }

      /* Main background */
      [data-testid="stAppViewContainer"] > .main {
        background-color: var(--background-gray) !important;
      }

      /* Sidebar */
      [data-testid="stSidebar"] {
        background-color: var(--white) !important;
      }

      /* Container */
      .main .block-container {
        max-width: 1200px;
        padding: 2.5rem 1.5rem;
        background-color: var(--background-gray) !important;
      }

      /* Headers with blue color */
      h1 {
        color: var(--primary-blue) !important;
        font-size: 2.5rem !important;
        font-weight: 800 !important;
        margin-bottom: 1.5rem !important;
      }

      h2 {
        color: var(--primary-blue) !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
        margin: 2rem 0 1.5rem 0 !important;
      }

      h3 {
        color: var(--primary-blue) !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        margin-bottom: 1rem !important;
      }

      /* Form labels */
      label {
        color: var(--primary-blue) !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
      }

      /* Input fields - LIGHT GRAY background */
      .stSelectbox select, 
      .stNumberInput input, 
      .stTextInput input,
      .stTextArea textarea {
        background-color: var(--light-gray) !important;
        border: 2px solid var(--border-gray) !important;
        border-radius: 10px !important;
        padding: 14px 18px !important;
        transition: all 0.2s ease !important;
        color: var(--text-dark) !important;
      }

      .stSelectbox select:focus, 
      .stNumberInput input:focus, 
      .stTextInput input:focus,
      .stTextArea textarea:focus {
        border-color: var(--primary-blue) !important;
        box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1) !important;
        background-color: var(--white) !important;
      }

      /* Select dropdown options - LIGHT GRAY */
      .stSelectbox select option {
        background-color: var(--light-gray) !important;
        color: var(--text-dark) !important;
        padding: 10px !important;
      }

      .stSelectbox select option:hover {
        background-color: var(--medium-gray) !important;
      }

      /* Radio buttons - LIGHT GRAY background */
      .stRadio > div {
        background-color: var(--light-gray) !important;
        border: 2px solid var(--border-gray) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        margin: 0.5rem 0 !important;
        transition: all 0.2s ease !important;
      }

      .stRadio > div:hover {
        border-color: var(--primary-blue) !important;
        background-color: var(--medium-gray) !important;
      }

      .stRadio > div[data-checked="true"] {
        background-color: var(--white) !important;
        border-color: var(--primary-blue) !important;
      }

      /* Buttons */
      .stButton > button {
        background: linear-gradient(135deg, var(--primary-blue) 0%, var(--sky-blue) 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 14px 32px !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        transition: all 0.2s ease !important;
        min-height: 48px !important;
      }

      .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(0, 102, 204, 0.3) !important;
      }

      /* Metrics - White background to stand out */
      .stMetric {
        background-color: var(--white) !important;
        border: 2px solid var(--border-gray) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
      }

      .stMetric:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1) !important;
      }

      .stMetric label {
        color: var(--text-grey) !important;
        font-size: 0.9rem !important;
      }

      .stMetric [data-testid="stMetricValue"] {
        color: var(--primary-blue) !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
      }

      /* Alerts */
      .stSuccess {
        background-color: rgba(0, 170, 102, 0.1) !important;
        border-left: 4px solid #00aa66 !important;
        border-radius: 8px !important;
        padding: 1rem !important;
      }

      .stError {
        background-color: rgba(204, 51, 51, 0.1) !important;
        border-left: 4px solid #cc3333 !important;
        border-radius: 8px !important;
        padding: 1rem !important;
      }

      .stInfo {
        background-color: var(--white) !important;
        border-left: 4px solid var(--primary-blue) !important;
        border-radius: 8px !important;
        padding: 1rem !important;
      }

      .stWarning {
        background-color: rgba(255, 153, 51, 0.1) !important;
        border-left: 4px solid #ff9933 !important;
        border-radius: 8px !important;
        padding: 1rem !important;
      }

      /* Dividers */
      hr {
        margin: 2rem 0 !important;
        border: none !important;
        border-top: 2px solid var(--border-gray) !important;
      }

      /* Links */
      a {
        color: var(--primary-blue) !important;
        text-decoration: none !important;
        font-weight: 600 !important;
      }

      a:hover {
        color: var(--deep-blue) !important;
        text-decoration: underline !important;
      }

      /* Form containers */
      .stForm {
        background-color: var(--white) !important;
        border: 1px solid var(--border-gray) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
      }

      /* ========================================================== */
      /* CRITICAL: FORCE SAME STRUCTURE ON ALL DEVICES             */
      /* Columns NEVER stack - they always stay side-by-side       */
      /* ========================================================== */
      
      /* Force horizontal layout - NEVER vertical */
      [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 0.5rem !important;
      }

      /* Force columns to stay side-by-side */
      [data-testid="column"] {
        display: flex !important;
        flex-direction: column !important;
        flex: 1 1 0 !important;
        min-width: 0 !important;
        width: auto !important;
        max-width: none !important;
      }

      /* Prevent any column from taking full width */
      [data-testid="column"] > div {
        width: 100% !important;
      }

      /* Force equal column distribution */
      [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex-grow: 1 !important;
        flex-shrink: 1 !important;
        flex-basis: 0 !important;
      }

      /* ========================================================== */
      /* RESPONSIVE DESIGN - SAME STRUCTURE, JUST SCALED            */
      /* Only text size and spacing change - layout stays same     */
      /* ========================================================== */
      
      /* Large Desktop (1920px+) */
      @media (min-width: 1920px) {
        .main .block-container {
          max-width: 1400px;
        }
      }

      /* Desktop & Laptop (1200px - 1919px) - DEFAULT */
      @media (min-width: 1200px) and (max-width: 1919px) {
        .main .block-container {
          max-width: 1200px;
        }
      }

      /* Laptop & Tablet Landscape (992px - 1199px) */
      @media (min-width: 992px) and (max-width: 1199px) {
        .main .block-container {
          max-width: 100%;
          padding: 2rem 1.5rem;
        }
        
        /* Scale text only - structure stays same */
        h1 { font-size: 2.25rem !important; }
        h2 { font-size: 1.875rem !important; }
        h3 { font-size: 1.375rem !important; }
        
        /* Columns still side-by-side with smaller gap */
        [data-testid="stHorizontalBlock"] {
          gap: 0.4rem !important;
        }
      }

      /* Tablet Portrait (768px - 991px) */
      @media (min-width: 768px) and (max-width: 991px) {
        .main .block-container {
          max-width: 100%;
          padding: 1.75rem 1.25rem;
        }
        
        /* Scale text - structure stays same */
        h1 { font-size: 2rem !important; }
        h2 { font-size: 1.75rem !important; }
        h3 { font-size: 1.25rem !important; }
        
        /* Columns still side-by-side */
        [data-testid="stHorizontalBlock"] {
          gap: 0.3rem !important;
        }
        
        /* Scale metrics */
        .stMetric {
          padding: 1.25rem !important;
        }
        
        .stMetric [data-testid="stMetricValue"] {
          font-size: 1.75rem !important;
        }
      }

      /* Mobile Landscape & Large Phone (576px - 767px) */
      @media (min-width: 576px) and (max-width: 767px) {
        .main .block-container {
          padding: 1.5rem 1rem;
        }
        
        /* Scale text - structure stays same */
        h1 { font-size: 1.75rem !important; }
        h2 { font-size: 1.5rem !important; }
        h3 { font-size: 1.15rem !important; }
        
        /* Columns STILL side-by-side with minimal gap */
        [data-testid="stHorizontalBlock"] {
          gap: 0.25rem !important;
        }
        
        /* Scale inputs */
        .stSelectbox select, 
        .stNumberInput input, 
        .stTextInput input {
          font-size: 0.9rem !important;
          padding: 12px 14px !important;
        }
        
        /* Scale labels */
        label {
          font-size: 0.85rem !important;
        }
        
        /* Scale metrics */
        .stMetric {
          padding: 1rem !important;
        }
        
        .stMetric [data-testid="stMetricValue"] {
          font-size: 1.5rem !important;
        }
        
        .stMetric label {
          font-size: 0.8rem !important;
        }
        
        /* Scale buttons */
        .stButton > button {
          font-size: 0.9rem !important;
          padding: 12px 24px !important;
        }
      }

      /* Mobile Portrait (up to 575px) - SMALLEST BUT SAME STRUCTURE */
      @media (max-width: 575px) {
        .main .block-container {
          padding: 1rem 0.75rem;
        }
        
        /* Scale text - structure stays same */
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.25rem !important; }
        h3 { font-size: 1.1rem !important; }
        
        /* Columns STILL side-by-side with minimal gap */
        [data-testid="stHorizontalBlock"] {
          gap: 0.15rem !important;
        }
        
        /* Scale inputs to fit */
        .stSelectbox select, 
        .stNumberInput input, 
        .stTextInput input {
          font-size: 0.8rem !important;
          padding: 10px 12px !important;
        }
        
        /* Scale labels */
        label {
          font-size: 0.8rem !important;
        }
        
        /* Scale metrics */
        .stMetric {
          padding: 0.75rem !important;
        }
        
        .stMetric [data-testid="stMetricValue"] {
          font-size: 1.25rem !important;
        }
        
        .stMetric label {
          font-size: 0.75rem !important;
        }
        
        /* Scale buttons */
        .stButton > button {
          font-size: 0.85rem !important;
          padding: 10px 20px !important;
          min-height: 42px !important;
        }
      }

      /* Extra safety: Override any Streamlit mobile defaults */
      @media (max-width: 640px) {
        [data-testid="stHorizontalBlock"] {
          flex-direction: row !important;
          flex-wrap: nowrap !important;
        }
        
        [data-testid="column"] {
          flex: 1 1 0 !important;
        }
      }

      /* ========================================================== */
      /* HORIZONTAL SCROLLING (if needed on very small screens)     */
      /* Prevents layout breaking - allows horizontal scroll        */
      /* ========================================================== */
      @media (max-width: 480px) {
        .main .block-container {
          overflow-x: auto !important;
        }
        
        [data-testid="stHorizontalBlock"] {
          min-width: fit-content !important;
        }
      }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def show_brand_bar(logo_path=LOGO_PATH):
    """Display the brand header bar"""
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

def show_progress_bar():
    """Display progress indicator"""
    progress = (st.session_state.current_page / (len(PAGES) - 1)) * 100
    st.markdown(f"""
    <div style="--progress: {progress}%" class="page-progress"></div>
    <div class="step-indicator">
        <div style="font-size: 14px; color: #10b981; font-weight: 600; margin-bottom: 0.5rem;">
            STEP {st.session_state.current_page + 1} OF {len(PAGES)}
        </div>
        <div style="font-size: 18px; font-weight: 600; color: #1e40af;">
            {PAGES[st.session_state.current_page]}
        </div>
    </div>
    """, unsafe_allow_html=True)

def navigation_buttons():
    """Display navigation buttons"""
    st.markdown("<div style='margin: 3rem 0 2rem 0;'>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.session_state.current_page > 0:
            if st.button("← Previous", use_container_width=True, key="nav_prev"):
                st.session_state.current_page -= 1
                st.rerun()
    
    with col3:
        if st.session_state.current_page < len(PAGES) - 1:
            if st.button("Next →", use_container_width=True, key="nav_next", type="primary"):
                st.session_state.current_page += 1
                st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)

# ==================== DECISION TREE & CALCULATIONS ====================

DT_THRESHOLDS = {
    "process_temp_min": 80.0,
    "process_temp_max": 200.0,
    "hp_target_max": 180.0,
    "steam_pressure_max": 10.0,
    "hot_air_ok_max": 110.0,
    "hot_air_caution_max": 150.0,
}

def evaluate_decision_tree(
    process_temp_c, energy_vector, target_supply_temp_c, steam_pressure_barA,
    has_waste_heat, waste_temp_known, waste_temp_c, waste_amount_known,
    waste_amount_pct_band, waste_heat_captured=None, has_waste_heat_processor=None,
    how_released=None, waste_form=None, humidity_ratio_known=None, q_waste_kw=None
):
    """Evaluate heat pump feasibility based on decision tree logic"""
    TH = DT_THRESHOLDS
    notes = []
    assumptions = {}

    # Validate inputs
    if process_temp_c is None or target_supply_temp_c is None:
        return {
            "status": "caution",
            "notes": ["Please provide all required temperature values."],
            "assumptions": {}
        }

    # Check process temperature range
    if process_temp_c < TH["process_temp_min"] or process_temp_c > TH["process_temp_max"]:
        return {
            "status": "not_viable",
            "notes": [f"Process temperature {process_temp_c:.0f}°C is outside the 80–200 °C window — heat pump not viable."],
            "assumptions": {}
        }

    # Check energy vector specific constraints
    e = str(energy_vector).lower()
    if e == "steam":
        if steam_pressure_barA is None:
            return {"status": "caution", "notes": ["Provide steam pressure (barA) to check heat-pump feasibility."], "assumptions": {}}
        if steam_pressure_barA > TH["steam_pressure_max"]:
            return {"status": "not_viable", "notes": [f"Steam pressure {steam_pressure_barA:.1f} barA > {TH['steam_pressure_max']} barA — heat pump not possible."], "assumptions": {}}
    elif e == "hot air":
        if target_supply_temp_c > TH["hp_target_max"]:
            return {"status": "not_viable", "notes": [f"Required hot-air temperature {target_supply_temp_c:.0f}°C > {TH['hp_target_max']}°C — heat pump not possible."], "assumptions": {}}
        if target_supply_temp_c > TH["hot_air_caution_max"]:
            return {"status": "not_viable", "notes": ["Hot air >150 °C — heat pump not recommended (consider heat exchangers)."], "assumptions": {}}
        if TH["hot_air_ok_max"] < target_supply_temp_c <= TH["hot_air_caution_max"]:
            notes.append("Hot air 110–150 °C — feasible but COP may be modest (high lift).")
    elif e == "hot water":
        if target_supply_temp_c > TH["hp_target_max"]:
            return {"status": "not_viable", "notes": [f"Required hot-water temperature {target_supply_temp_c:.0f}°C > {TH['hp_target_max']}°C — heat pump not possible."], "assumptions": {}}

    # Check waste heat availability
    if not has_waste_heat:
        return {"status": "suggest_hx", "notes": ["No waste heat identified — this may be better suited to direct heat recovery via heat exchangers."], "assumptions": {}}

    # Check how waste heat is released
    if how_released == "General ventilation in the production area":
        return {"status": "not_viable", "notes": ["Waste heat only available via general room ventilation — better suited to heat recovery through heat exchangers than a heat pump."], "assumptions": {}}
    elif how_released == "Dedicated cooling system or exhaust pipe":
        notes.append("Waste heat from a dedicated cooling system or exhaust — suitable for heat-pump integration.")

    # Determine waste heat temperature
    if waste_temp_known and (waste_temp_c is not None):
        assumptions["T_in1"] = float(waste_temp_c)
    else:
        assumptions["T_in1"] = float(process_temp_c)
        notes.append("Waste-heat temperature unknown — assuming equal to process temperature.")

    # Determine waste heat amount
    if waste_amount_known and q_waste_kw is not None and q_waste_kw > 0:
        assumptions["Q_waste_kW"] = float(q_waste_kw)
        notes.append(f"Using user-provided waste heat level Q_waste ≈ {q_waste_kw:.0f} kW.")
    else:
        band = waste_amount_pct_band or "31–50% of energy input"
        try:
            band_clean = band.split("of")[0].strip()
            if "–" in band_clean:
                hi_str = band_clean.split("–")[1]
            else:
                hi_str = "50"
            hi = int("".join(ch for ch in hi_str if ch.isdigit()) or "50")
        except:
            hi = 50
        assumptions["waste_pct"] = hi
        notes.append(f"Waste-heat amount unknown — using upper estimate ≈ {hi}% of energy input.")

    # Waste form specific notes
    if waste_form:
        assumptions["waste_form"] = waste_form
        form_notes = {
            "Humid air": "Waste heat available as humid air — heat pump integration possible, with final sizing refined at design stage.",
            "Dry hot air": "Waste heat available as dry hot air — suitable for heat pump via an air-to-refrigerant heat exchanger.",
            "Hot water": "Waste heat available as hot water — highly suitable for heat-pump integration.",
            "Pure steam": "Waste heat available as pure steam — heat pump integration possible with suitable condenser design."
        }
        if waste_form in form_notes:
            notes.append(form_notes[waste_form])

    # Waste heat capture status
    if waste_heat_captured == "Yes":
        notes.append("Waste heat is already captured — integration may be simpler and cheaper.")
    elif waste_heat_captured == "No":
        notes.append("Waste heat not yet captured — additional pipework/ducting or a heat exchanger may be needed.")

    # Existing waste heat processor
    if has_waste_heat_processor == "Yes":
        notes.append("There is already a waste-heat processing system on site (e.g. ORC or heat-recovery unit).")
    elif has_waste_heat_processor == "No":
        notes.append("No existing waste-heat processor — Mechapres could be the main technology to use that heat.")

    return {"status": "proceed" if not notes else "caution", "notes": notes, "assumptions": assumptions}

def excel_performance_logic(T_in1, T_out2, P_out2, Q_process, 
                            T_app_condenser=8.0, T_app_evaporator=8.0, 
                            T_ev_minimum=70.0, lorentz_eff=0.60, 
                            waste_heat_min_pct=30.0, waste_heat_max_pct=60.0):
    """Calculate heat pump performance metrics"""
    
    # Validation
    if Q_process <= 0:
        raise ValueError("Q_process must be greater than 0")
    if T_in1 is None or T_out2 is None:
        raise ValueError("Temperature values cannot be None")
    
    # Calculate temperatures
    T_cond_steam = T_out2 + T_app_condenser - 2.0
    T_evap_raw = T_in1 - T_app_evaporator
    T_evap = max(T_evap_raw, T_ev_minimum)

    # Calculate COP
    if T_cond_steam <= T_evap:
        COP_carnot = 0.0
    else:
        TcK, TeK = T_cond_steam + 273.15, T_evap + 273.15
        COP_carnot = TcK / (TcK - TeK)

    COP_real = max(0.0, lorentz_eff * COP_carnot)
    
    # Calculate waste heat requirements
    wh_min = Q_process * (waste_heat_min_pct / 100.0)
    wh_max = Q_process * (waste_heat_max_pct / 100.0)
    
    # Calculate electrical consumption
    E_full = (Q_process / COP_real) if COP_real > 0 else float("inf")
    E_min = E_full / 2.0 if math.isfinite(E_full) else float("inf")
    
    Q2_min = wh_min
    Q2_max = wh_max
    capacity_MWth = Q_process / 1000.0

    return {
        "T_cond_steam": T_cond_steam,
        "T_evap": T_evap,
        "COP_carnot": COP_carnot,
        "COP_real": COP_real,
        "waste_heat_min_kW": wh_min,
        "waste_heat_max_kW": wh_max,
        "E_min_kW": E_min,
        "E_max_kW": E_full,
        "Q2_min_kW": Q2_min,
        "Q2_max_kW": Q2_max,
        "capacity_MWth": capacity_MWth
    }

# ==================== PDF GENERATION ====================

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

def generate_report(inputs, results, logo_path=LOGO_PATH, brand=MECHAPRES_COLORS):
    """Generate PDF report"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header
    c.setFillColor(colors.HexColor("#ffffff"))
    c.rect(0, height - 100, width, 100, stroke=0, fill=1)
    if logo_path:
        try:
            c.drawImage(logo_path, 40, height - 85, width=100, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    c.setFillColor(colors.HexColor(brand["primary"]))
    c.setFont("Helvetica-Bold", 15)
    c.drawString(160, height - 60, "Industrial Heat Pump Estimation Report")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(160, height - 78, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    c.setStrokeColor(colors.HexColor(brand["primary"]))
    c.line(40, height - 100, width - 40, height - 100)

    # Contact details
    y = height - 125
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Contact Details")
    y -= 16
    c.setFont("Helvetica", 9)
    for label, key in [("Name", "contact_name"), ("Company", "contact_company"), 
                       ("Email", "contact_email"), ("Phone", "contact_phone")]:
        val = inputs.get(key)
        if val:
            c.drawString(60, y, f"{label}: {val}")
            y -= 12
    consent_txt = "Yes" if inputs.get("contact_consent") else "No"
    c.drawString(60, y, f"Consent to contact: {consent_txt}")
    y -= 14

    # Results summary
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor(brand["primary"]))
    c.drawString(40, y, "Results Summary")
    c.setFillColor(colors.black)
    y -= 16
    c.setFont("Helvetica", 9)
    summary_lines = [
        ("Annual Cost Savings (high case, £)", f"{results.get('savings_high', 0):,.0f}"),
        ("CO₂ Reduction (t/year)", f"{results.get('co2_savings', 0):,.0f}"),
        ("Simple Payback (high case, years)", f"{results.get('payback_high', 0):.1f}"),
    ]
    for k, v in summary_lines:
        c.drawString(60, y, f"{k}: {v}")
        y -= 12

    # Disclaimer
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.HexColor(MECHAPRES_COLORS["muted"]))
    c.drawString(40, y - 20, "Disclaimer: Indicative estimates only. For detailed feasibility, contact info@mechapres.co.uk.")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def generate_quick_estimate_pdf(process_temp, energy_vector, heat_supply_tech, fuel_type,
                                savings_high, savings_low, payback_high, payback_low, 
                                irr_high, irr_low, co2_savings, cost_current, cost_mechapres,
                                co2_current, co2_mechapres, capex_high, capex_low,
                                logo_path=LOGO_PATH, brand=MECHAPRES_COLORS):
    """Generate Quick Estimate PDF (no contact info required)"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Header with logo
    c.setFillColor(colors.HexColor(brand["primary"]))
    c.rect(0, height - 80, width, 80, stroke=0, fill=1)
    
    if logo_path:
        try:
            c.drawImage(logo_path, 40, height - 70, width=80, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(140, height - 45, "Quick Heat Pump Estimate")
    c.setFont("Helvetica", 10)
    c.drawString(140, height - 63, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Start content
    y = height - 110
    
    # Process Parameters
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Process Parameters")
    y -= 20
    
    c.setFont("Helvetica", 10)
    params = [
        ("Process Temperature:", f"{process_temp}°C"),
        ("Energy Vector:", energy_vector),
        ("Heat Supply Technology:", heat_supply_tech),
        ("Fuel Type:", fuel_type)
    ]
    for label, value in params:
        c.drawString(60, y, f"{label}")
        c.drawString(250, y, value)
        y -= 15
    
    y -= 10
    
    # Financial Results - High Case
    c.setFillColor(colors.HexColor(brand["primary"]))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Financial Results (High Case)")
    y -= 20
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    high_case = [
        ("Annual Cost Savings:", f"£{savings_high:,.0f}"),
        ("Simple Payback Period:", f"{payback_high:.1f} years"),
        ("Internal Rate of Return (IRR):", f"{irr_high:.0f}%")
    ]
    for label, value in high_case:
        c.drawString(60, y, label)
        c.drawString(250, y, value)
        y -= 15
    
    y -= 10
    
    # Financial Results - Low Case
    c.setFillColor(colors.HexColor(brand["secondary"]))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Financial Results (Low Case)")
    y -= 20
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    low_case = [
        ("Annual Cost Savings:", f"£{savings_low:,.0f}"),
        ("Simple Payback Period:", f"{payback_low:.1f} years"),
        ("Internal Rate of Return (IRR):", f"{irr_low:.0f}%")
    ]
    for label, value in low_case:
        c.drawString(60, y, label)
        c.drawString(250, y, value)
        y -= 15
    
    y -= 10
    
    # Current System
    c.setFillColor(colors.HexColor(brand["error"]))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Current System")
    y -= 20
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    current = [
        ("Annual Energy Cost:", f"£{cost_current:,.0f}"),
        ("Annual CO₂ Emissions:", f"{co2_current:,.0f} tonnes")
    ]
    for label, value in current:
        c.drawString(60, y, label)
        c.drawString(250, y, value)
        y -= 15
    
    y -= 10
    
    # With Mechapres Heat Pump
    c.setFillColor(colors.HexColor(brand["success"]))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "With Mechapres Heat Pump")
    y -= 20
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    mechapres = [
        ("Annual Energy Cost:", f"£{cost_mechapres:,.0f}"),
        ("Annual CO₂ Emissions:", f"{co2_mechapres:,.0f} tonnes"),
        ("CO₂ Reduction:", f"{co2_savings:,.0f} tonnes/year")
    ]
    for label, value in mechapres:
        c.drawString(60, y, label)
        c.drawString(250, y, value)
        y -= 15
    
    y -= 10
    
    # Investment
    c.setFillColor(colors.HexColor(brand["primary"]))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Investment Estimate")
    y -= 20
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    investment = [
        ("Estimated CapEx (High Case):", f"£{capex_high:,.0f}"),
        ("Estimated CapEx (Low Case):", f"£{capex_low:,.0f}")
    ]
    for label, value in investment:
        c.drawString(60, y, label)
        c.drawString(250, y, value)
        y -= 15
    
    # Disclaimer box at bottom
    y = 100
    c.setFillColor(colors.HexColor(brand["light_blue"]))
    c.rect(40, y - 40, width - 80, 60, stroke=1, fill=1)
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y + 5, "DISCLAIMER")
    c.setFont("Helvetica", 8)
    
    disclaimer_text = [
        "This is an indicative estimate only. For detailed feasibility analysis and custom quotation,",
        "please contact info@mechapres.co.uk or visit www.mechapres.co.uk",
        "",
        "For a comprehensive PDF report with charts and detailed analysis, please provide your",
        "contact details in the dashboard to receive our detailed report."
    ]
    
    y -= 5
    for line in disclaimer_text:
        c.drawString(50, y, line)
        y -= 10
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ==================== EMAIL FUNCTIONALITY ====================

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate

def send_email_with_pdf(subject, body, to_addr, pdf_bytes, pdf_filename):
    """Send email with PDF attachment"""
    try:
        host = st.secrets["SMTP_HOST"]
        port = int(st.secrets["SMTP_PORT"])
        user = st.secrets["SMTP_USER"]
        pwd = st.secrets["SMTP_PASS"]
    except Exception:
        raise RuntimeError("SMTP secrets missing. Add them in .streamlit/secrets.toml")
    
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to_addr
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=pdf_filename)
    
    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, pwd)
        server.send_message(msg)

# ==================== MAIN APPLICATION ====================

st.set_page_config(page_title="Mechapres Industrial Heat Pump Calculator", layout="wide")
apply_brand_theme()
show_brand_bar()

if st.session_state.current_page > 0:
    show_progress_bar()

# ==================== PAGE ROUTING ====================

current_page = PAGES[st.session_state.current_page]

if current_page == "Welcome":
    # Clean welcome page
    st.markdown("""
    <div style='text-align: center; padding: 3rem 2rem;'>
        <h1 style='color: #0066cc; font-size: 3rem; margin-bottom: 1.5rem;'>
            Mechapres Heat Pump Calculator
        </h1>
        <p style='color: #4d4d4d; font-size: 1.25rem; line-height: 1.8; margin-bottom: 3rem;'>
            Assess the feasibility and benefits of high-temperature heat pumps for your industrial process
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Blue banner with key benefits
    st.markdown("""
    <div style='background: linear-gradient(135deg, #0066cc 0%, #3399ff 100%); 
                padding: 3rem 2rem; 
                border-radius: 20px; 
                margin-bottom: 3rem;
                text-align: center;
                box-shadow: 0 10px 40px rgba(0, 102, 204, 0.3);'>
        <h2 style='color: white; font-size: 2rem; margin-bottom: 1.5rem;'>
            Industrial Heat Pump Solutions
        </h2>
        <p style='color: white; font-size: 1.25rem; line-height: 1.8; margin: 0;'>
            High-temperature heat pumps for steam and hot water generation up to 150°C
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # What you get from calculator
    st.markdown("## What This Calculator Provides")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown("""
        ✅ **Technical Feasibility Assessment**  
        ✅ **Energy Cost Analysis**  
        ✅ **ROI & Payback Period**
        """)
    
    with col_b:
        st.markdown("""
        ✅ **Carbon Emission Reduction**  
        ✅ **Investment Estimates**  
        ✅ **Downloadable PDF Report**
        """)
    
    st.markdown("---")
    
    # CTA
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Start Assessment", key="get_quote", use_container_width=True, type="primary"):
            st.session_state.current_page = 1
            st.rerun()
    
    st.info("**Complete the assessment in approximately 5 minutes**")



elif current_page == "Basic Site Parameters":
    st.title("Basic Site Parameters")
    st.markdown("Tell us about your industrial process and current heat supply.")

    colA, colB = st.columns(2)
    
    st.session_state.process_temp = colA.number_input(
        "Process temperature (°C)",
        20.0, 300.0,
        value=st.session_state.process_temp,
        step=1.0,
        format="%.0f",
        help="Typical operating temperature of your industrial process that needs heat."
    )
    
    st.session_state.energy_vector = colB.selectbox(
        "Energy vector used to provide heat",
        ["Steam", "Hot Water", "Hot Air"],
        index=["Steam", "Hot Water", "Hot Air"].index(st.session_state.energy_vector),
        help="The main medium currently used to supply heat to your process."
    )

    st.session_state.heat_supply_tech = st.selectbox(
        "How are you providing heat to the process?",
        ["Fossil fuel boiler", "Electric boiler", "Industrial heat pump", "Combined heat and power", "Other"],
        index=["Fossil fuel boiler", "Electric boiler", "Industrial heat pump", "Combined heat and power", "Other"].index(st.session_state.heat_supply_tech),
        help="Select the main technology currently providing heat to this process."
    )

    colC, colD = st.columns(2)
    
    st.session_state.T_out2 = colC.number_input(
        "Required supply temperature (°C)",
        50.0, 250.0,
        value=st.session_state.T_out2,
        step=1.0,
        format="%.0f"
    )
    
    if st.session_state.energy_vector == "Steam":
        st.session_state.steam_p = colD.number_input(
            "Steam supply pressure (barA)",
            1.0, 20.0,
            value=st.session_state.steam_p,
            step=1.0,
            format="%.0f",
            help="Operating pressure of your steam line in bar absolute."
        )

    colD1, colD2 = st.columns(2)
    
    st.session_state.prod_days = colD1.number_input(
        "Days of production per year",
        1, 365,
        value=st.session_state.prod_days,
        help="How many days in a typical year your process is running."
    )
    
    st.session_state.prod_hours_per_day = colD2.number_input(
        "Hours of production per day",
        1, 24,
        value=st.session_state.prod_hours_per_day,
        help="Average number of hours per production day that the process is running."
    )

    operating_hours_est = calculate_operating_hours()
        # st.info(f"**Operating hours per year:** {operating_hours_est:.0f} h/year")  # Hidden per user request

    # Demand & Energy Prices Section
    st.markdown("---")
    st.markdown("### 💰 Demand & Energy Prices")
    st.markdown("Help us calculate your potential savings by providing energy costs and consumption.")

    heat_supply_tech = st.session_state.heat_supply_tech
    uses_fuel = system_uses_fuel(heat_supply_tech)
    
    st.markdown(f"**Current heat supply technology:** {heat_supply_tech}")
    st.markdown("---")
    
    if not uses_fuel:
        st.info("ℹ️ **Note:** Electric-based systems don't require fuel inputs. Only electricity pricing is needed below.")

    # Fuel inputs (only for fuel-based systems)
    if uses_fuel:
        e2, e3 = st.columns(2)
        
        st.session_state.fuel_type = e2.selectbox(
            "Fuel type used by the current system",
            FUEL_OPTIONS,
            index=FUEL_OPTIONS.index(st.session_state.fuel_type) if st.session_state.fuel_type in FUEL_OPTIONS else 3
        )

        st.session_state.fuel_price = e3.number_input(
            "Fuel cost (£/MWh)",
            0.0, 300.0,
            value=st.session_state.fuel_price
        )

    # Electricity and efficiency
    e4, e5 = st.columns(2)
    
    st.session_state.electricity_price = e4.number_input(
        "Electricity cost (£/MWh)",
        0.0, 300.0,
        value=st.session_state.electricity_price
    )
    
    # Suggest efficiency based on heat supply technology
    suggested_eff = get_efficiency_default(heat_supply_tech)
    
    st.session_state.boiler_eff_pct = e5.number_input(
        "Existing system efficiency (%)",
        40.0, 100.0,
        value=suggested_eff if st.session_state.boiler_eff_pct == 80.0 else st.session_state.boiler_eff_pct,
        step=1.0,
        format="%.0f",
        help="Typical values: 80% for fossil fuel boilers, 95% for electric boilers, 90% for CHP or heat pumps (use design COP for industrial heat pumps)."
    )

    # Store efficiency as decimal
    st.session_state.boiler_eff = st.session_state.boiler_eff_pct / 100.0

    # Annual Energy Costs Section
    st.markdown("---")
    st.markdown("### 📊 Annual Energy Costs (Scale of Site)")
    st.markdown("This helps us understand the scale of your operation for better recommendations.")

    band_options = ["<£100k", "£100k–£500k", ">£500k"]
    st.session_state.annual_band = st.radio(
        "Approximate annual energy spend category",
        band_options,
        index=band_options.index(st.session_state.annual_band),
        horizontal=True
    )

    # Display emission factors
    heat_supply_tech = st.session_state.heat_supply_tech
    uses_fuel = system_uses_fuel(heat_supply_tech)
    
    fuel_type = st.session_state.fuel_type
    emission_factor_fuel_kWh = FUEL_EMISSION_FACTORS_KG_PER_KWH.get(fuel_type, 0.2027)
    emission_factor_elec = ELECTRICITY_CO2_KG_PER_MWH
    
    if uses_fuel:
        st.info(f"**Emission factors used:** {emission_factor_fuel_kWh:.3f} kgCO₂/kWh for {fuel_type} and {emission_factor_elec:.0f} kgCO₂/MWh for electricity")
    else:
        st.info(f"**Emission factors used:** {emission_factor_elec:.0f} kgCO₂/MWh for electricity (comparing to {emission_factor_fuel_kWh:.3f} kgCO₂/kWh natural gas baseline)")

    # Calculate Q_process
    if uses_fuel:
        unit_cost_baseline = st.session_state.fuel_price
    else:
        unit_cost_baseline = st.session_state.electricity_price
    
    operating_hours = st.session_state.operating_hours
    yearly_cost = st.session_state.yearly_cost
    boiler_eff = st.session_state.boiler_eff

    Q_process_calculated = 100.0
    if unit_cost_baseline > 0 and operating_hours > 0:
        try:
            energy_purchased_MWh = yearly_cost / unit_cost_baseline
            useful_MWh = energy_purchased_MWh * boiler_eff
            Q_process_calculated = max(10.0, useful_MWh * 1000.0 / operating_hours)
        except (ZeroDivisionError, ValueError):
            Q_process_calculated = 100.0

    # Initialize manual override flag if not set
    if "q_process_manual_override" not in st.session_state:
        st.session_state.q_process_manual_override = False
    
    # Display calculated value with option to manually override
    st.markdown("---")
    st.markdown("#### 🔧 Process Heat Demand")
    
    st.info(f"💡 **Calculated estimate:** {Q_process_calculated:,.0f} kW (based on your annual energy spend and system efficiency)")
    
    # Ask if user wants to manually change it
    st.session_state.q_process_manual_override = st.radio(
        "**Do you want to manually change this value?**",
        ["No, use the calculated estimate", "Yes, I want to enter my own value"],
        index=1 if st.session_state.q_process_manual_override else 0,
        help="This is the estimated average process heat demand, based on your answers. You can accept our calculation or enter your own value if you have more accurate data."
    )
    
    manual_override = (st.session_state.q_process_manual_override == "Yes, I want to enter my own value")
    
    if manual_override:
        # Show editable input
        Q_process = st.number_input(
            "Enter your process heat demand (kW)",
            10.0, 50000.0,
            value=st.session_state.get("Q_process", Q_process_calculated),
            help="Enter the average thermal power required for your industrial process."
        )
        st.success("✅ Using your manually entered value")
    else:
        # Use calculated value, show as metric
        Q_process = Q_process_calculated
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.metric(
                "Estimated Average Process Heat Demand", 
                f"{Q_process:,.0f} kW",
                help="This value is calculated from your annual energy spend and system efficiency"
            )
        st.success("✅ Using calculated estimate based on your inputs")

    # Store calculated values
    st.session_state.Q_process = Q_process
    st.session_state.emission_factor_fuel_kWh = emission_factor_fuel_kWh
    st.session_state.emission_factor_elec = emission_factor_elec

    # Process Model - Simple Process Flow Only
    st.markdown("---")
    st.subheader("📊 Process Model")
    
    # Get temperature values from customer inputs
    process_temp = st.session_state.process_temp
    supply_temp = st.session_state.T_out2
    return_temp = process_temp - 15
    
    # PROCESS HEAT FLOW (Matching updated sketch)
    st.markdown("#### Process Heat Flow")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Process Exhausts (Top)
    st.markdown(f"""
    <div style='text-align: center; margin-bottom: 1.5rem;'>
        <div style='color: #ff9933; font-size: 2.8rem; line-height: 1; margin-bottom: 0.3rem;'>↑</div>
        <div style='font-size: 0.95rem; font-weight: 600; color: #ff9933;'>Process Exhausts</div>
        <div style='font-size: 0.8rem; color: #666;'>(waste heat)</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Main layout with columns
    col_left, col_center, col_right = st.columns([1.2, 1.5, 0.5])
    
    with col_left:
        # Heat Supply Temperature - TOP-LEFT of box
        st.markdown(f"""
        <div style='text-align: right; padding-right: 0.3rem;'>
            <div style='font-size: 0.9rem; font-weight: 600; color: #0066cc; margin-bottom: 0.4rem;'>Heat Supply Temperature</div>
            <div style='font-size: 1.4rem; font-weight: bold; color: #0066cc; margin-bottom: 0.5rem;'>{supply_temp:.0f}°C</div>
            <div style='color: #cc3333; font-size: 3rem; line-height: 1;'>→</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Spacer between arrows - adjusted for proper alignment
        st.markdown("<div style='height: 60px;'></div>", unsafe_allow_html=True)
        
        # Heat Return Temperature - BOTTOM-LEFT of box (aligned with box bottom)
        st.markdown(f"""
        <div style='text-align: right; padding-right: 0.3rem;'>
            <div style='color: #cc3333; font-size: 3rem; line-height: 1; margin-bottom: 0.5rem;'>←</div>
            <div style='font-size: 1.4rem; font-weight: bold; color: #0066cc; margin-bottom: 0.4rem;'>{return_temp:.0f}°C</div>
            <div style='font-size: 0.9rem; font-weight: 600; color: #0066cc;'>Heat Return Temperature</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_center:
        # Process Temperature Box
        st.markdown(f"""
        <div style='
            padding: 2.8rem 2.2rem;
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            border: 3px solid #0066cc;
            border-radius: 12px;
            box-shadow: 0 6px 16px rgba(0, 102, 204, 0.18);
            text-align: center;
            margin: 0 auto;
        '>
            <div style='color: #0066cc; font-size: 1.3rem; font-weight: 600; margin-bottom: 0.8rem; line-height: 1.2;'>Process Temperature</div>
            <div style='color: #0066cc; font-size: 3.2rem; font-weight: bold; line-height: 1;'>{process_temp:.0f}°C</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_right:
        # Empty column for spacing
        st.write("")
    
    st.markdown("<br>", unsafe_allow_html=True)

    navigation_buttons()


elif current_page == "Waste Heat":
    st.title("Waste Heat Assessment")
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); 
                padding: 1rem 1.25rem; 
                border-radius: 8px; 
                border-left: 4px solid #2563eb;
                margin-bottom: 1.25rem;'>
        <p style='margin: 0; font-size: 15px; color: #1e40af; line-height: 1.5;'>
            <strong>🔍 Why this matters:</strong> Understanding your waste heat streams is crucial for determining 
            heat pump viability and sizing. This assessment helps us identify the best recovery strategy for your facility.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🎯 Waste Heat Availability")
    
    st.session_state.has_waste = st.radio(
        "**Do you have waste heat from your current processes?**",
        ["Yes", "No"],
        index=["Yes", "No"].index(st.session_state.has_waste),
        help="Waste heat = heat that is currently rejected to air, water, or a cooling system and is not fully used in your process.",
        horizontal=True
    )

    if st.session_state.has_waste == "Yes":
        st.markdown("<div style='margin: 1rem 0;'></div>", unsafe_allow_html=True)
        
        # Section 1: Release Method
        st.markdown("""
        <div style='background: #ffffff; 
                    padding: 1rem 1.25rem; 
                    border-radius: 8px; 
                    border: 2px solid #e5e7eb;
                    margin-bottom: 1rem;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
            <h4 style='margin: 0 0 0.75rem 0; color: #1f2937; font-size: 16px;'>📤 1. Waste Heat Release Method</h4>
        """, unsafe_allow_html=True)
        
        st.session_state.how_released = st.selectbox(
            "How is the waste heat currently released?",
            ["Dedicated cooling system or exhaust pipe",
             "General ventilation in the production area",
             "Other / Not sure"],
            index=["Dedicated cooling system or exhaust pipe",
                   "General ventilation in the production area",
                   "Other / Not sure"].index(st.session_state.how_released),
            help="If not captured through an exhaust pipe it might not be possible to recover it."
        )
        
        st.markdown("</div>", unsafe_allow_html=True)

        # Section 2: Temperature Information
        st.markdown("""
        <div style='background: #ffffff; 
                    padding: 1rem 1.25rem; 
                    border-radius: 8px; 
                    border: 2px solid #e5e7eb;
                    margin-bottom: 1rem;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
            <h4 style='margin: 0 0 0.75rem 0; color: #1f2937; font-size: 16px;'>🌡️ 2. Temperature Information</h4>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.session_state.w_temp_known = st.radio(
                "Do you know the waste heat temperature?",
                ["Yes", "No"],
                index=["Yes", "No"].index(st.session_state.w_temp_known),
                help="If Yes, please provide the value. If No, we'll use the process temperature."
            )
        
        with col2:
            if st.session_state.w_temp_known == "Yes":
                st.session_state.w_temp = st.number_input(
                    "Waste heat temperature (°C)",
                    0.0, 250.0,
                    value=st.session_state.w_temp,
                    step=1.0,
                    format="%.0f",
                    help="The temperature of your waste heat stream"
                )
            else:
                st.markdown("<div style='padding-top: 1.5rem;'></div>", unsafe_allow_html=True)
                st.info("💡 We'll use your process temperature as an estimate")
        
        st.markdown("</div>", unsafe_allow_html=True)

        # Section 3: Quantity Information
        st.markdown("""
        <div style='background: #ffffff; 
                    padding: 1rem 1.25rem; 
                    border-radius: 8px; 
                    border: 2px solid #e5e7eb;
                    margin-bottom: 1rem;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
            <h4 style='margin: 0 0 0.75rem 0; color: #1f2937; font-size: 16px;'>⚡ 3. Quantity Information</h4>
        """, unsafe_allow_html=True)
        
        col3, col4 = st.columns([1, 1])
        
        with col3:
            st.session_state.w_amt_known = st.radio(
                "Do you know the amount of waste heat available?",
                ["Yes", "No"],
                index=["Yes", "No"].index(st.session_state.w_amt_known),
                help="Yes if you know the thermal power or flow rate of the waste stream."
            )

        with col4:
            if st.session_state.w_amt_known == "Yes":
                st.session_state.q_waste_kw = st.number_input(
                    "Waste heat available (kW)",
                    0.0, 100000.0,
                    value=st.session_state.q_waste_kw,
                    step=1.0,
                    format="%.0f",
                    help="The thermal power of your waste heat stream"
                )
            else:
                st.session_state.w_amt_band = st.selectbox(
                    "Estimate as % of energy input",
                    ["10-30% (very efficient process)", "31-50% (average for modern processes)", "51-80% (Typical for processes without any control for minimising waste heat)"],
                    index=["10-30% (very efficient process)", "31-50% (average for modern processes)", "51-80% (Typical for processes without any control for minimising waste heat)"].index(st.session_state.w_amt_band) if st.session_state.w_amt_band in ["10-30% (very efficient process)", "31-50% (average for modern processes)", "51-80% (Typical for processes without any control for minimising waste heat)"] else 1,
                    help="Estimate what fraction of your total energy input is ultimately rejected as waste heat."
                )
        
        st.markdown("</div>", unsafe_allow_html=True)

        # Section 4: Current Utilization
        st.markdown("""
        <div style='background: #ffffff; 
                    padding: 1rem 1.25rem; 
                    border-radius: 8px; 
                    border: 2px solid #e5e7eb;
                    margin-bottom: 1rem;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
            <h4 style='margin: 0 0 0.75rem 0; color: #1f2937; font-size: 16px;'>🔄 4. Current Waste Heat Utilization</h4>
        """, unsafe_allow_html=True)
        
        st.session_state.has_waste_heat_processor = st.radio(
            "Do you have existing waste heat recovery equipment?",
            ["Yes", "No"],
            index=["Yes", "No"].index(st.session_state.has_waste_heat_processor),
            help="Select Yes if you already have equipment that uses waste heat (e.g. a heat recovery unit or ORC)."
        )
        
        st.markdown("</div>", unsafe_allow_html=True)

        # Section 5: Waste Heat Medium Type
        st.markdown("""
        <div style='background: #ffffff; 
                    padding: 1rem 1.25rem; 
                    border-radius: 8px; 
                    border: 2px solid #e5e7eb;
                    margin-bottom: 1rem;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
            <h4 style='margin: 0 0 0.75rem 0; color: #1f2937; font-size: 16px;'>🧪 5. Waste Heat Medium Type</h4>
        """, unsafe_allow_html=True)
        
        st.markdown("**Select the form of your waste heat. This determines the heat exchanger design for your heat pump.**")
        
        form_options = ["Humid air", "Dry hot air", "Hot water", "Pure steam", "Don't know"]
        
        st.session_state.waste_form = st.selectbox(
            "Waste heat medium:",
            form_options,
            index=form_options.index(st.session_state.waste_form) if st.session_state.waste_form in form_options else 2,
            help="Select the form that best matches your waste heat stream."
        )

        # Medium-specific guidance
        waste_form = st.session_state.waste_form
        if waste_form == "Hot water":
            st.success("✅ Hot water waste streams provide the best heat transfer efficiency and are ideal for heat pump integration.")
        elif waste_form == "Pure steam":
            st.success("✅ **Very good choice!** Steam condensation provides excellent heat transfer characteristics and high efficiency.")
        elif waste_form == "Dry hot air":
            st.info("ℹ️ **Good option.** Air-to-refrigerant heat exchangers work well, though efficiency may be slightly lower than liquid streams.")
        elif waste_form == "Humid air":
            st.warning("⚠️ **Feasible but requires careful design.** Humid air can work well but needs consideration for condensation and corrosion management.")

        if waste_form == "Humid air":
            st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
            st.markdown("**💧 Humidity Information**")
            st.session_state.humidity_ratio_known = st.radio(
                "Do you know the humidity ratio of the waste air?",
                ["Yes", "No"],
                index=["Yes", "No"].index(st.session_state.humidity_ratio_known),
                help="If unknown, we'll use typical values and refine them during the detailed design phase."
            )
            
            if st.session_state.humidity_ratio_known == "Yes":
                st.success("💡 **Great!** Having humidity data helps us design more accurate heat recovery systems.")
            else:
                st.info("💡 **No problem.** We'll estimate typical humidity values for your application.")
        
        st.markdown("</div>", unsafe_allow_html=True)

        # Preliminary Feasibility Assessment
        st.markdown("<div style='margin: 1.5rem 0;'></div>", unsafe_allow_html=True)
        
        process_temp = st.session_state.process_temp
        T_out2 = st.session_state.T_out2
        energy_vector = st.session_state.energy_vector
        waste_temp = st.session_state.w_temp if st.session_state.w_temp_known == "Yes" else process_temp
        
        gate = evaluate_decision_tree(
            process_temp_c=process_temp,
            energy_vector=energy_vector,
            target_supply_temp_c=T_out2,
            steam_pressure_barA=st.session_state.steam_p if energy_vector == "Steam" else None,
            has_waste_heat=(st.session_state.has_waste == "Yes"),
            waste_temp_known=(st.session_state.w_temp_known == "Yes"),
            waste_temp_c=waste_temp,
            waste_amount_known=(st.session_state.w_amt_known == "Yes"),
            waste_amount_pct_band=st.session_state.w_amt_band,
            waste_heat_captured=st.session_state.waste_heat_captured,
            has_waste_heat_processor=st.session_state.has_waste_heat_processor,
            how_released=st.session_state.how_released,
            waste_form=waste_form if waste_form != "Don't know" else None,
            humidity_ratio_known=st.session_state.humidity_ratio_known,
            q_waste_kw=st.session_state.q_waste_kw if st.session_state.w_amt_known == "Yes" else None
        )
        st.session_state._gate = gate

        st.markdown("### ✅ Preliminary Feasibility Assessment")
        if gate["status"] == "not_viable":
            st.error("❌ **Not suitable for heat pump applications**")
            st.markdown("**Reasons:**")
            for note in gate["notes"]:
                st.write(f"• {note}")
        elif gate["status"] == "suggest_hx":
            st.warning("⚠️ **Heat exchanger may be more suitable than a heat pump**")
            st.markdown("**Considerations:**")
            for note in gate["notes"]:
                st.write(f"• {note}")
        elif gate["status"] == "caution":
            st.info("✅ **Heat pump is feasible with some considerations**")
            st.markdown("**Notes:**")
            for note in gate["notes"]:
                st.write(f"• {note}")
        else:
            st.success("✅ **Excellent heat pump application!**")
            st.markdown("**Advantages identified:**")
            for note in gate["notes"]:
                st.write(f"• {note}")
        
    else:
        st.markdown("<div style='margin: 1rem 0;'></div>", unsafe_allow_html=True)
        st.warning("""
        ⚠️ **No waste heat available**
        
        Heat pumps work best when waste heat is available to provide the base heat source. 
        Without waste heat, you might want to consider:
        - Direct electric heating solutions
        - Air-source heat pumps (if applicable for your temperature requirements)
        - Other decarbonization technologies
        
        We can still help you explore options - please continue with the assessment.
        """)

    navigation_buttons()

elif current_page == "Investment Variables":
    st.title("Investment Variables")
    st.markdown("Set the cost assumptions for your heat pump investment analysis.")

    inv1, inv2 = st.columns(2)
    
    st.session_state.design_pm = inv1.number_input(
        "Design and project management (£)",
        0.0, 10_000_000.0,
        value=st.session_state.design_pm,
        help="Indicative allowance for design and project management."
    )
    
    st.session_state.fixed_install = inv2.number_input(
        "Fixed installation costs (£)",
        0.0, 10_000_000.0,
        value=st.session_state.fixed_install,
        help="Base installation costs that do not scale with heat-pump size."
    )

    inv3, inv4, inv5 = st.columns(3)
    
    st.session_state.hp_cost_per_kw = inv3.number_input(
        "Heat pump cost (£/kW)",
        0.0, 5_000.0,
        value=st.session_state.hp_cost_per_kw
    )
    
    st.session_state.hr_cost_per_kw = inv4.number_input(
        "Heat recovery system cost (£/kW)",
        0.0, 5_000.0,
        value=st.session_state.hr_cost_per_kw
    )
    
    st.session_state.var_install_per_kw = inv5.number_input(
        "Variable installation costs (£/kW)",
        0.0, 5_000.0,
        value=st.session_state.var_install_per_kw
    )

    navigation_buttons()

elif current_page == "Investment & Returns":
    st.title("Investment & Returns")
    
    try:
        # Get values
        gate = st.session_state.get("_gate", {"assumptions": {}})
        T_in1 = gate["assumptions"].get("T_in1", st.session_state.w_temp if st.session_state.w_temp_known == "Yes" else st.session_state.process_temp)
        T_out2 = st.session_state.T_out2
        Q_process = st.session_state.Q_process
        
        # Validate
        if Q_process <= 0:
            st.error("❌ Invalid process heat demand. Please go back and check your inputs.")
            if st.button("← Go Back to Basic Site Parameters"):
                st.session_state.current_page = 1
                st.rerun()
            st.stop()
        
        # Calculate performance
        waste_pct_assumed = gate["assumptions"].get("waste_pct", 40)
        waste_min_pct = max(10, min(90, waste_pct_assumed - 10))
        waste_max_pct = max(waste_min_pct + 5, min(100, waste_pct_assumed + 10))

        perf = excel_performance_logic(
            T_in1=T_in1,
            T_out2=T_out2,
            P_out2=5.0,
            Q_process=Q_process,
            waste_heat_min_pct=waste_min_pct,
            waste_heat_max_pct=waste_max_pct
        )

        if perf["COP_real"] <= 0:
            st.error("❌ COP calculation failed. The temperature lift may be too high for a heat pump. Please review your temperature inputs.")
            if st.button("← Go Back to Review Temperatures"):
                st.session_state.current_page = 1
                st.rerun()
            st.stop()

        # Economic calculations
        operating_hours = st.session_state.operating_hours
        electricity_price = st.session_state.electricity_price
        boiler_eff = st.session_state.boiler_eff
        
        heat_supply_tech = st.session_state.heat_supply_tech
        uses_fuel = system_uses_fuel(heat_supply_tech)
        
        if uses_fuel:
            current_energy_price = st.session_state.fuel_price
        else:
            current_energy_price = electricity_price
        
        Q_steam_MWh = (Q_process * operating_hours) / 1000.0
        E_hp_electric_MWh = Q_steam_MWh / perf["COP_real"]
        E_current_MWh = Q_steam_MWh / boiler_eff

        cost_current = E_current_MWh * current_energy_price
        cost_mechapres = E_hp_electric_MWh * electricity_price
        annual_savings_high = cost_current - cost_mechapres

        # CO2 calculations
        emission_factor_elec = st.session_state.emission_factor_elec
        
        if uses_fuel:
            emission_factor_fuel_kWh = st.session_state.emission_factor_fuel_kWh
            co2_current = E_current_MWh * emission_factor_fuel_kWh
        else:
            co2_current = E_current_MWh * emission_factor_elec / 1000.0
        
        co2_mechapres = E_hp_electric_MWh * emission_factor_elec / 1000.0
        co2_savings = max(0, co2_current - co2_mechapres)

        # Investment calculations
        design_pm = st.session_state.design_pm
        fixed_install = st.session_state.fixed_install
        hp_cost_per_kw = st.session_state.hp_cost_per_kw
        hr_cost_per_kw = st.session_state.hr_cost_per_kw
        var_install_per_kw = st.session_state.var_install_per_kw

        hp_size_high_kw = max(250.0, perf["capacity_MWth"] * 1000.0)
        hp_size_low_kw = max(250.0, hp_size_high_kw / 2.0)
        hr_size_high_kw = 0.66 * hp_size_high_kw
        hr_size_low_kw = 0.66 * hp_size_low_kw

        def total_investment(hp_kw, hr_kw):
            variable_cost = hp_kw * hp_cost_per_kw + hr_kw * hr_cost_per_kw + (hp_kw + hr_kw) * var_install_per_kw
            return design_pm + fixed_install + variable_cost

        capex_low = total_investment(hp_size_low_kw, hr_size_low_kw)
        capex_high = total_investment(hp_size_high_kw, hr_size_high_kw)

        savings_high = max(annual_savings_high, 0.0)
        savings_low = max(0.15 * savings_high, 0.0)

        def simple_payback(capex, savings):
            return capex / savings if savings > 0 else float("inf")

        def irr_from_savings(capex, savings, years=10):
            if savings <= 0:
                return 0.0
            low_r, high_r = 0.0, 1.0
            for _ in range(60):
                r = (low_r + high_r) / 2
                npv = -capex
                for t in range(1, years + 1):
                    npv += savings / ((1 + r) ** t)
                if npv > 0:
                    low_r = r
                else:
                    high_r = r
            return (low_r + high_r) / 2 * 100.0

        payback_low = simple_payback(capex_low, savings_low)
        payback_high = simple_payback(capex_high, savings_high)
        irr_low = irr_from_savings(capex_low, savings_low, years=10)
        irr_high = irr_from_savings(capex_high, savings_high, years=10)

        # Display results
        st.subheader("💰 Savings Range")
        s1, s2 = st.columns(2)
        
        with s1:
            st.markdown("**Annual savings — low case**")
            st.markdown(f"### £{savings_low:,.0f}")
            st.caption("Conservative case with smaller heat-pump size.")
        
        with s2:
            st.markdown("**Annual savings — high case**")
            st.markdown(f"### £{savings_high:,.0f}")
            st.caption("Larger heat-pump project capturing more savings.")

        st.subheader("📦 Investment and Returns")
        colL, colH = st.columns(2)

        with colL:
            st.markdown("**Low Case**")
            st.write(f"Total investment cost: **£{capex_low:,.0f}**")
            # Format payback period
            if math.isfinite(payback_low) and payback_low <= 10:
                st.write(f"Simple payback: **{payback_low:.1f} years**")
            else:
                st.write(f"Simple payback: **>10 years**")
            st.write(f"IRR (10 years): **{irr_low:.0f}%**")

        with colH:
            st.markdown("**High Case**")
            st.write(f"Total investment cost: **£{capex_high:,.0f}**")
            # Format payback period
            if math.isfinite(payback_high) and payback_high <= 10:
                st.write(f"Simple payback: **{payback_high:.1f} years**")
            else:
                st.write(f"Simple payback: **>10 years**")
            st.write(f"IRR (10 years): **{irr_high:.0f}%**")

        st.caption("Note: For projects below ~250 kW, alternative solutions may be more suitable.")

        # Calculate cash flow data (needed for Key Financial Insights)
        def calculate_cash_flow(capex, annual_savings, years=10):
            cash_flow = [-capex]
            cumulative = [-capex]
            for year in range(1, years + 1):
                cash_flow.append(annual_savings)
                cumulative.append(cumulative[-1] + annual_savings)
            return cash_flow, cumulative
        
        cf_low, cum_low = calculate_cash_flow(capex_low, savings_low, 10)
        cf_high, cum_high = calculate_cash_flow(capex_high, savings_high, 10)
        years = list(range(0, 11))
        
        def find_breakeven(cumulative):
            for i, val in enumerate(cumulative):
                if val >= 0:
                    return i
            return None
        
        breakeven_low = find_breakeven(cum_low)
        breakeven_high = find_breakeven(cum_high)

        # Key Financial Insights (moved here, reformatted)
        st.markdown("---")
        st.subheader("💡 Key Financial Insights")
        insight_col1, insight_col2, insight_col3 = st.columns(3)
        
        with insight_col1:
            st.markdown("**High Case — Net Position (Year 10)**")
            st.markdown(f"### £{cum_high[-1]:,.0f}")
            if cum_high[-1] > 0:
                st.caption(f"£{cum_high[-1] + capex_high:,.0f} profit")
        
        with insight_col2:
            st.markdown("**Low Case — Net Position (Year 10)**")
            st.markdown(f"### £{cum_low[-1]:,.0f}")
            if cum_low[-1] > 0:
                st.caption(f"£{cum_low[-1] + capex_low:,.0f} profit")
        
        with insight_col3:
            avg_roi = ((cum_high[-1] + capex_high) / capex_high * 100) if capex_high > 0 else 0
            st.markdown("**Average ROI (High Case)**")
            st.markdown(f"### {avg_roi:.1f}%")
            st.caption("Return on Investment over 10 years")

        # Cash flow analysis
        st.markdown("---")
        st.subheader("📊 10-Year Cash Flow Analysis")
        st.markdown("Visualize your investment returns over time with cumulative cash flow projections.")
        
        # Create charts
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        fig.patch.set_facecolor('none')
        
        # High Case
        ax1.fill_between(years, cum_high, 0, where=[y >= 0 for y in cum_high],
                         alpha=0.7, color=MECHAPRES_COLORS["success"], label='Positive Return',
                         interpolate=True)
        ax1.fill_between(years, cum_high, 0, where=[y < 0 for y in cum_high],
                         alpha=0.7, color=MECHAPRES_COLORS["error"], label='Investment Period',
                         interpolate=True)
        ax1.plot(years, cum_high, linewidth=2.5, color=MECHAPRES_COLORS["primary"],
                marker='o', markersize=6, label='Cumulative Cash Flow')
        ax1.axhline(y=0, color=MECHAPRES_COLORS["text"], linestyle='-', linewidth=2, alpha=0.8)
        
        if breakeven_high is not None:
            ax1.plot(breakeven_high, cum_high[breakeven_high], 'g*',
                    markersize=20, label=f'Break-even (Year {breakeven_high})', zorder=5)
            ax1.annotate(f'Break-even\nYear {breakeven_high}',
                        xy=(breakeven_high, cum_high[breakeven_high]),
                        xytext=(breakeven_high + 1, cum_high[breakeven_high] * 1.2 if cum_high[breakeven_high] > 0 else cum_high[breakeven_high] * 0.8),
                        fontsize=10, fontweight='bold', color=MECHAPRES_COLORS["success"],
                        arrowprops=dict(arrowstyle='->', color=MECHAPRES_COLORS["success"], lw=2))
        
        ax1.set_xlabel('Year', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Cumulative Cash Flow (£)', fontsize=12, fontweight='bold')
        ax1.set_title('High Case - 10-Year Projection', fontsize=14, fontweight='bold',
                     color=MECHAPRES_COLORS["primary"], pad=15)
        ax1.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
        ax1.legend(loc='best', framealpha=0.95, fontsize=9)
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'£{x/1000:.0f}k'))
        ax1.set_xlim(-0.5, 10.5)
        
        # Low Case
        ax2.fill_between(years, cum_low, 0, where=[y >= 0 for y in cum_low],
                         alpha=0.7, color=MECHAPRES_COLORS["success"], label='Positive Return',
                         interpolate=True)
        ax2.fill_between(years, cum_low, 0, where=[y < 0 for y in cum_low],
                         alpha=0.7, color=MECHAPRES_COLORS["error"], label='Investment Period',
                         interpolate=True)
        ax2.plot(years, cum_low, linewidth=2.5, color=MECHAPRES_COLORS["secondary"],
                marker='o', markersize=6, label='Cumulative Cash Flow')
        ax2.axhline(y=0, color=MECHAPRES_COLORS["text"], linestyle='-', linewidth=2, alpha=0.8)
        
        if breakeven_low is not None:
            ax2.plot(breakeven_low, cum_low[breakeven_low], 'g*',
                    markersize=20, label=f'Break-even (Year {breakeven_low})', zorder=5)
            ax2.annotate(f'Break-even\nYear {breakeven_low}',
                        xy=(breakeven_low, cum_low[breakeven_low]),
                        xytext=(breakeven_low + 1, cum_low[breakeven_low] * 1.2 if cum_low[breakeven_low] > 0 else cum_low[breakeven_low] * 0.8),
                        fontsize=10, fontweight='bold', color=MECHAPRES_COLORS["success"],
                        arrowprops=dict(arrowstyle='->', color=MECHAPRES_COLORS["success"], lw=2))
        
        ax2.set_xlabel('Year', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Cumulative Cash Flow (£)', fontsize=12, fontweight='bold')
        ax2.set_title('Low Case - 10-Year Projection', fontsize=14, fontweight='bold',
                     color=MECHAPRES_COLORS["secondary"], pad=15)
        ax2.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
        ax2.legend(loc='best', framealpha=0.95, fontsize=9)
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'£{x/1000:.0f}k'))
        ax2.set_xlim(-0.5, 10.5)
        
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
        
        # Cash flow table
        with st.expander("📋 View Detailed Cash Flow Table", expanded=False):
            st.markdown("### Cash Flow Breakdown")
            
            col_table1, col_table2 = st.columns(2)
            
            with col_table1:
                st.markdown("#### High Case")
                df_high = pd.DataFrame({
                    'Year': years,
                    'Annual Cash Flow': [f"£{val:,.0f}" for val in cf_high],
                    'Cumulative': [f"£{val:,.0f}" for val in cum_high]
                })
                st.dataframe(df_high, use_container_width=True, hide_index=True)
                
                if breakeven_high:
                    st.success(f"✅ **Break-even in Year {breakeven_high}**")
                    st.write(f"Total return after 10 years: **£{cum_high[-1]:,.0f}**")
                else:
                    st.warning("⚠️ Break-even not reached within 10 years")
            
            with col_table2:
                st.markdown("#### Low Case")
                df_low = pd.DataFrame({
                    'Year': years,
                    'Annual Cash Flow': [f"£{val:,.0f}" for val in cf_low],
                    'Cumulative': [f"£{val:,.0f}" for val in cum_low]
                })
                st.dataframe(df_low, use_container_width=True, hide_index=True)
                
                if breakeven_low:
                    st.success(f"✅ **Break-even in Year {breakeven_low}**")
                    st.write(f"Total return after 10 years: **£{cum_low[-1]:,.0f}**")
                else:
                    st.warning("⚠️ Break-even not reached within 10 years")
        
        # Store results
        st.session_state._final_results = {
            "savings_high": savings_high,
            "savings_low": savings_low,
            "payback_high": payback_high,
            "payback_low": payback_low,
            "irr_high": irr_high,
            "irr_low": irr_low,
            "co2_savings": co2_savings,
            "cost_current": cost_current,
            "cost_mechapres": cost_mechapres,
            "co2_current": co2_current,
            "co2_mechapres": co2_mechapres,
            "capex_high": capex_high,
            "capex_low": capex_low,
            "cash_flow_high": cf_high,
            "cash_flow_low": cf_low,
            "cumulative_high": cum_high,
            "cumulative_low": cum_low,
            "breakeven_high": breakeven_high,
            "breakeven_low": breakeven_low,
        }

        # Results Section (integrated from Step 5)
        st.markdown("---")
        st.markdown("---")
        st.title("🎯 Your Heat Pump Estimate")
        
        # Main metrics
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**Annual savings (high case)**")
            st.markdown(f"### £{savings_high:,.0f}")
        
        with c2:
            # Format payback period consistently
            if math.isfinite(payback_high) and payback_high <= 10:
                payback_display = f"{payback_high:.1f} years"
            else:
                payback_display = ">10 years"
            st.markdown("**Simple payback (high case)**")
            st.markdown(f"### {payback_display}")

        with st.expander("Low vs high case comparison", expanded=False):
            payback_low_str = f"{payback_low:.1f} years" if (math.isfinite(payback_low) and payback_low <= 10) else ">10 years"
            payback_high_str = f"{payback_high:.1f} years" if (math.isfinite(payback_high) and payback_high <= 10) else ">10 years"
            
            st.write(f"**Low case** — savings £{savings_low:,.0f}/year, "
                     f"payback {payback_low_str}, IRR {irr_low:.0f}%")
            st.write(f"**High case** — savings £{savings_high:,.0f}/year, "
                     f"payback {payback_high_str}, IRR {irr_high:.0f}%")

        # Environmental impact
        st.subheader("🌍 Environmental Impact")
        st.markdown("**CO₂ Reduction**")
        st.markdown(f"### {co2_savings:,.0f} tonnes/year")

        # Quick Estimate Download (No contact info required)
        st.markdown("---")
        st.subheader("📊 Quick Estimate Download")
        st.markdown("Download your estimate summary instantly - no contact details required.")
        
        # Generate Quick Estimate PDF
        try:
            quick_pdf_buffer = generate_quick_estimate_pdf(
                process_temp=st.session_state.process_temp,
                energy_vector=st.session_state.energy_vector,
                heat_supply_tech=st.session_state.heat_supply_tech,
                fuel_type=st.session_state.fuel_type,
                savings_high=savings_high,
                savings_low=savings_low,
                payback_high=payback_high,
                payback_low=payback_low,
                irr_high=irr_high,
                irr_low=irr_low,
                co2_savings=co2_savings,
                cost_current=cost_current,
                cost_mechapres=cost_mechapres,
                co2_current=co2_current,
                co2_mechapres=co2_mechapres,
                capex_high=capex_high,
                capex_low=capex_low
            )
            quick_pdf_bytes = quick_pdf_buffer.getvalue()
            quick_pdf_filename = f"Mechapres_Quick_Estimate_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            
            # Single centered download button
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col2:
                st.download_button(
                    label="📥 Download Quick Estimate (PDF)",
                    data=quick_pdf_bytes,
                    file_name=quick_pdf_filename,
                    mime="application/pdf",
                    use_container_width=True,
                    help="Download a PDF with your key results - no registration required"
                )
        
        except Exception as pdf_error:
            st.error(f"Error generating Quick Estimate PDF: {str(pdf_error)}")
            st.info("Please contact info@mechapres.co.uk for assistance.")

        # Contact form
        st.markdown("---")
        st.header("📇 Get Your Detailed PDF Report")
        st.markdown("*For a comprehensive PDF report with charts and analysis, please provide your contact details below.*")
        
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
                        st.success("Contact details saved!")
                        st.session_state.contact_name = name
                        st.session_state.contact_company = company
                        st.session_state.contact_email = email
                        st.session_state.contact_phone = phone
                        st.session_state.contact_consent = consent
                        st.session_state.show_contact = False
                        st.rerun()
        else:
            if st.button("📋 Enter Contact Details", key="show_contact_btn", use_container_width=True):
                st.session_state.show_contact = True
                st.rerun()

        # PDF generation with better error handling
        name = st.session_state.get("contact_name", "")
        company = st.session_state.get("contact_company", "")
        email = st.session_state.get("contact_email", "")
        phone = st.session_state.get("contact_phone", "")
        consent = st.session_state.get("contact_consent", False)

        if name and email:
            try:
                gate = st.session_state.get("_gate", {"notes": []})
                inputs_for_pdf = {
                    "Process_temperature_C": st.session_state.process_temp,
                    "Energy_vector": st.session_state.energy_vector,
                    "Heat_supply_technology": st.session_state.heat_supply_tech,
                    "Fuel_type": st.session_state.fuel_type,
                    "contact_name": name,
                    "contact_company": company,
                    "contact_email": email,
                    "contact_phone": phone,
                    "contact_consent": consent
                }

                results_for_pdf = {
                    "savings_high": savings_high,
                    "co2_savings": co2_savings,
                    "payback_high": payback_high,
                    "cost_current": cost_current,
                    "cost_mechapres": cost_mechapres,
                    "co2_current": co2_current,
                    "co2_mechapres": co2_mechapres,
                    "messages": gate.get("notes", [])
                }

                pdf_buffer = generate_report(inputs_for_pdf, results_for_pdf)
                pdf_bytes = pdf_buffer.getvalue()
                fname = f"Mechapres_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

                col1, col2 = st.columns(2)
                
                with col1:
                    st.download_button("📥 Download PDF Report", data=pdf_bytes, file_name=fname, mime="application/pdf", use_container_width=True)
                    
                with col2:
                    if st.button("📧 Email Report to Me", use_container_width=True):
                        if consent:
                            try:
                                send_email_with_pdf(
                                    "Your Mechapres Heat Pump Estimate",
                                    f"Hi {name},\n\nAttached is your Mechapres industrial heat pump estimate.\n\nBest regards,\nMechapres",
                                    email, pdf_bytes, fname
                                )
                                st.success("Report emailed successfully!")
                            except Exception as e:
                                st.error(f"Email failed: {str(e)}")
                        else:
                            st.warning("Please provide consent to email the report.")
            
            except Exception as pdf_error:
                st.error(f"Error generating PDF report: {str(pdf_error)}")
                st.info("Please try downloading the Quick Estimate above, or contact info@mechapres.co.uk for assistance.")

        # Restart
        st.divider()
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Start New Estimate", use_container_width=True):
                # Clear all session state
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

    except Exception as e:
        st.error(f"❌ Error in calculations: {str(e)}")
        st.write("Please review your inputs in previous steps.")
        with st.expander("Debug Information"):
            st.write(f"Error details: {type(e).__name__}: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

    navigation_buttons()
