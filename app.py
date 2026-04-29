import streamlit as st
import ee
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from google.oauth2 import service_account
from sklearn.ensemble import RandomForestRegressor
import folium
from streamlit_folium import st_folium

# =========================================================
# CONFIGURATION & PAGE SETUP
# =========================================================
st.set_page_config(
    page_title="A-DAM | Hydro-Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🛰"
)

# INITIALIZE SECURITY STATE
if 'system_compromised' not in st.session_state:
    st.session_state.system_compromised = False

# =========================================================
# ADVANCED CUSTOM DESIGN (DARK MODE HUD UI)
# =========================================================
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
    .stApp {
        background-color: #020617;
        background-image: 
            radial-gradient(circle at 15% 50%, rgba(6, 182, 212, 0.08), transparent 25%), 
            radial-gradient(circle at 85% 30%, rgba(99, 102, 241, 0.08), transparent 25%);
        color: #e2e8f0;
        font-family: 'Rajdhani', sans-serif;
    }
    h1, h2, h3, h4, .stMarkdown {
        font-family: 'Rajdhani', sans-serif;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    .metric-value, .stCode, code, pre {
        font-family: 'JetBrains Mono', monospace;
    }
    [data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 1px solid #1e293b;
    }
    .hud-card {
        background: rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(30, 41, 59, 0.8);
        border-left: 3px solid #06b6d4;
        border-radius: 6px;
        padding: 16px;
        margin-bottom: 12px;
        transition: all 0.3s ease;
    }
    .sat-frame {
        position: relative;
        border: 1px solid #334155;
        padding: 4px;
        background: #000;
        border-radius: 4px;
    }
    .status-dot {
        height: 10px; width: 10px;
        background-color: #22c55e;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 10px #22c55e;
        animation: pulse 2s infinite;
    }
    .status-dot-red {
        background-color: #ef4444;
        box-shadow: 0 0 10px #ef4444;
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
        70% { box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); }
        100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
    }
</style>
""", unsafe_allow_html=True)

# HEADER WITH SECURITY LOGIC
status_label = "SYS.ONLINE" if not st.session_state.system_compromised else "SYS.COMPROMISED"
status_color = "#22c55e" if not st.session_state.system_compromised else "#ef4444"
dot_class = "status-dot" if not st.session_state.system_compromised else "status-dot status-dot-red"

col1, col2, col3 = st.columns([6, 2, 1])
with col1:
    st.markdown('<h1 style="margin:0; font-size: 2.5rem; color:#fff;">A-DAM</h1>', unsafe_allow_html=True)
    st.markdown('<div style="color:#94a3b8; font-size: 0.9rem; letter-spacing: 1px;">ALGERIAN DAMS INTELLIGENCE • MONITORING & FORECASTING</div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'''
    <div style="text-align:right; margin-top:15px;">
        <div style="color:{status_color}; font-size:0.75rem; display:flex; align-items:center; justify-content:flex-end; gap:5px;">
            <span class="{dot_class}"></span> {status_label}
        </div>
        <div style="color:#64748b; font-family:\'JetBrains Mono\'; font-size:0.75rem;">V.2.4.2</div>
    </div>
    ''', unsafe_allow_html=True)

# =========================================================
# AUTHENTICATION & DATABASE
# =========================================================
@st.cache_resource
def login_to_gee():
    try:
        # ✅ MODIFIÉ : lit la clé depuis les Secrets Streamlit Cloud
        gee_secrets = dict(st.secrets["gee"])
        credentials = service_account.Credentials.from_service_account_info(
            gee_secrets,
            scopes=['https://www.googleapis.com/auth/earthengine.readonly']
        )
        ee.Initialize(credentials)
        return True
    except Exception as e:
        return False

DAMS_DB = {
    "Adrar: Timiaouine": [0.35, 20.43], "Chlef: Sidi Yakoub": [1.25, 36.05], "Chlef: Oued Fodda": [1.46, 36.13],
    "Laghouat: Seklafa": [2.55, 33.68], "Laghouat: Tadjmout": [2.53, 33.88], "Oum El Bouaghi: Ourkis": [6.61, 35.91],
    "Batna: Koudiet Lamdaouar": [6.46, 35.53], "Batna: Maafa": [5.92, 35.29], "Batna: Bouzina": [6.13, 35.27],
    "Bejaia: Tichy-Haf": [4.81, 36.42], "Bejaia: Ighil Emda": [5.18, 36.48], "Biskra: Foum El Gherza": [5.91, 34.85],
    "Biskra: Fontaine des Gazelles": [5.62, 35.15], "Algiers: Douera": [2.90, 36.66], "Algiers: El Hamiz": [3.35, 36.65],
    "Algiers/Boumerdes: Keddara": [3.42, 36.65], "Djelfa: Ain Maabed": [3.12, 34.82], "Djelfa: Charef": [2.82, 34.61],
    "Djelfa: Oum Eddhrou": [3.28, 34.66], "Jijel: Kissir": [5.67, 36.80], "Jijel: Boussiaba": [6.24, 36.72],
    "Jijel: El Agrem": [5.60, 36.76], "Jijel: Erraguene": [5.33, 36.63], "Jijel: Tabellout": [5.97, 36.56],
    "Setif: Mahouane": [5.31, 36.25], "Setif: Draa Diss": [5.52, 36.21], "Saida: Kef Bouali": [0.18, 34.91],
    "Skikda: Zerdezas": [6.83, 36.58], "Skikda: Guenitra": [6.48, 36.87], "Skikda: Zit Emba": [6.95, 36.70],
    "Skikda: Beni Zid": [6.59, 36.89], "Sidi Bel Abbes: Sarno": [-0.47, 35.28], "Sidi Bel Abbes: Sidi Abdelli": [-1.02, 35.03],
    "Sidi Bel Abbes: Bouhanifia": [-0.05, 35.31], "Annaba/Tarf: Mexa": [8.41, 36.80], "Annaba/Tarf: Cheffia": [8.02, 36.61],
    "Annaba/Tarf: Bougous": [8.39, 36.65], "Mila: Beni Haroun": [6.26, 36.55], "Bouira: Koudiat Acerdoune": [3.77, 36.45],
    "Tizi Ouzou: Taksebt": [4.13, 36.67], "Ain Defla: Ghrib": [2.53, 36.14], "Medea: Boughezoul": [2.86, 35.70]
}

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("### MISSION CONTROL")
    selected_dam = st.selectbox("Select Dam Target", list(DAMS_DB.keys()))
    coords = DAMS_DB[selected_dam]
    
    if st.button("⚡ REFRESH DATA STREAM", use_container_width=True):
        st.cache_data.clear()
        st.session_state.system_compromised = False
        st.rerun()

    st.markdown("---")
    if st.button("☣️ INJECT SYSTEM ANOMALY", type="secondary", use_container_width=True):
        st.session_state.system_compromised = True
        st.rerun()

# =========================================================
# DATA ENGINE
# =========================================================
@st.cache_data(ttl=1800)
def fetch_live_data(lon, lat):
    point = ee.Geometry.Point([lon, lat])
    water_aoi = point.buffer(1500)
    aoi_buffer = point.buffer(5000)
    today = datetime.now().strftime('%Y-%m-%d')

    s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
          .filterBounds(point).filterDate('2023-01-01', today)
          .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)))

    def add_indices(img):
        ndti = img.normalizedDifference(['B4', 'B3']).rename('NDTI')
        ndwi = img.normalizedDifference(['B3', 'B8']).rename('NDWI')
        return img.addBands([ndti, ndwi])

    processed = s2.map(add_indices)

    def extract_stats(img):
        stats = img.reduceRegion(reducer=ee.Reducer.mean(), geometry=water_aoi, scale=10)
        return ee.Feature(None, {
            'date': img.date().format('YYYY-MM-dd'),
            'NDTI': stats.get('NDTI'),
            'NDWI': stats.get('NDWI'),
            'time': img.get('system:time_start')
        })

    try:
        features = processed.map(extract_stats).filter(ee.Filter.notNull(['NDTI'])).getInfo()['features']
        df = pd.DataFrame([f['properties'] for f in features])
        df['date'] = pd.to_datetime(df['date'])
        
        latest_img = processed.sort('system:time_start', False).first()
        last_acq = datetime.utcfromtimestamp(latest_img.get('system:time_start').getInfo() / 1000).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # CHIRPS Rain
        chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY').filterBounds(aoi_buffer).filterDate(df['date'].min().strftime('%Y-%m-%d'), today)
        rain_f = chirps.map(lambda i: ee.Feature(None, {'date': i.date().format('YYYY-MM-dd'), 'rainfall_mm': i.reduceRegion(ee.Reducer.mean(), aoi_buffer, 5000).get('precipitation')})).getInfo()['features']
        rain_df = pd.DataFrame([f['properties'] for f in rain_f])
        rain_df['date'] = pd.to_datetime(rain_df['date'])
        df = df.merge(rain_df, on='date', how='left').fillna(0)
        
        return df.sort_values('date'), latest_img, last_acq, None
    except Exception as e:
        return pd.DataFrame(), None, None, str(e)


# =========================================================
# HELPER: COLOR RISK LEVEL CELLS IN DATAFRAME
# =========================================================
def style_risk_column(df, risk_col):
    """Return a Styler that colors the Risk Level column red/green."""
    def color_risk(val):
        if val == "High":
            return 'background-color: #7f1d1d; color: #fca5a5; font-weight: bold;'
        else:
            return 'background-color: #14532d; color: #86efac; font-weight: bold;'
    return df.style.map(color_risk, subset=[risk_col])


if login_to_gee():
    lon, lat = coords[0], coords[1]
    df, latest_image, last_acquisition, error_msg = fetch_live_data(lon, lat)

    if not df.empty:
        # SECURITY OVERRIDE
        latest_row = df.iloc[-1]
        current_ndti = 5.0 if st.session_state.system_compromised else latest_row['NDTI']
        current_ndwi = latest_row['NDWI']
        
        if st.session_state.system_compromised:
            st.error("🚨 CRITICAL: ISOLATION FOREST DETECTED COMPROMISED DATA STREAM. STATUS: INSECURE.")

        tab1, tab2, tab3 = st.tabs([" LIVE FEED", " PREDICTIVE AI", " INTELLIGENCE"])

        # =================================================
        # TAB 1 — LIVE FEED
        # =================================================
        with tab1:
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown('<div class="section-header">SATELLITE VIEW</div>', unsafe_allow_html=True)
                region = ee.Geometry.Point([lon, lat]).buffer(3500).bounds()
                url = latest_image.getThumbURL({'bands':['B4','B3','B2'], 'min':0, 'max':3000, 'region':region, 'dimensions':1024})
                st.markdown(f'<div class="sat-frame"><img src="{url}" style="width:100%;"></div>', unsafe_allow_html=True)

            with c2:
                st.markdown('<div class="section-header">TELEMETRY</div>', unsafe_allow_html=True)

                acq_display = last_acquisition if last_acquisition else "N/A"
                st.markdown(
                    f'<div class="hud-card" style="border-left-color:#a855f7">'
                    f'<div style="font-size:0.75rem; color:#94a3b8;">LAST IMAGE ACQUIRED</div>'
                    f'<div class="metric-value" style="font-size:1rem; color:#d8b4fe; word-break:break-all;">{acq_display}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                ndti_color = "#ef4444" if st.session_state.system_compromised else "#e11d48"
                st.markdown(f'<div class="hud-card" style="border-left-color:{ndti_color}"><div style="font-size:0.75rem;">NDTI (Turbidity)</div><div class="metric-value" style="font-size:1.8rem; color:{ndti_color}">{current_ndti:.4f}</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="hud-card"><div style="font-size:0.75rem;">NDWI (Water)</div><div class="metric-value" style="font-size:1.8rem; color:#3b82f6">{current_ndwi:.4f}</div></div>', unsafe_allow_html=True)
            
            st.markdown('<div class="section-header">GEOLOCATION</div>', unsafe_allow_html=True)
            m = folium.Map(location=[lat, lon], zoom_start=12, tiles='cartodbdark_matter')
            folium.Circle([lat, lon], radius=1500, color='#06b6d4', fill=True).add_to(m)
            st_folium(m, width=1200, height=400)

        # =================================================
        # TAB 2 — PREDICTIVE AI
        # =================================================
        with tab2:
            st.markdown('<div class="section-header">7-DAY FORECAST ENGINE</div>', unsafe_allow_html=True)

            for lag in [1, 2, 3]:
                df[f'NDTI_lag{lag}'] = df['NDTI'].shift(lag)
                df[f'NDWI_lag{lag}'] = df['NDWI'].shift(lag)
                df[f'rain_lag{lag}'] = df['rainfall_mm'].shift(lag)
            
            df_ml = df.dropna()

            if len(df_ml) > 10:
                feature_cols = (
                    [f'NDTI_lag{i}' for i in [1,2,3]] +
                    [f'NDWI_lag{i}' for i in [1,2,3]] +
                    [f'rain_lag{i}' for i in [1,2,3]]
                )

                model_ndti = RandomForestRegressor(n_estimators=100, random_state=42)
                model_ndti.fit(df_ml[feature_cols], df_ml['NDTI'])

                model_ndwi = RandomForestRegressor(n_estimators=100, random_state=42)
                model_ndwi.fit(df_ml[feature_cols], df_ml['NDWI'])

                future_dates = [datetime.now().date() + timedelta(days=i) for i in range(1, 8)]

                preds_ndti = []
                last_row = df[['NDTI', 'NDWI', 'rainfall_mm']].iloc[-3:].values.flatten().tolist()
                last_lags_ndti = last_row
                for _ in range(7):
                    p = model_ndti.predict([last_lags_ndti])[0]
                    preds_ndti.append(p)
                    last_lags_ndti = [p] + last_lags_ndti[:-1]

                preds_ndwi = []
                last_lags_ndwi = df[['NDTI', 'NDWI', 'rainfall_mm']].iloc[-3:].values.flatten().tolist()
                for _ in range(7):
                    p = model_ndwi.predict([last_lags_ndwi])[0]
                    preds_ndwi.append(p)
                    last_lags_ndwi = [p] + last_lags_ndwi[:-1]

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df['date'], y=df['NDTI'], name="NDTI Historical", line=dict(color='#3b82f6')))
                fig.add_trace(go.Scatter(x=future_dates, y=preds_ndti, name="NDTI AI Forecast", line=dict(color='#22d3ee', dash='dot')))
                fig.add_trace(go.Scatter(x=df['date'], y=df['NDWI'], name="NDWI Historical", line=dict(color='#a855f7')))
                fig.add_trace(go.Scatter(x=future_dates, y=preds_ndwi, name="NDWI AI Forecast", line=dict(color='#f0abfc', dash='dot')))

                if st.session_state.system_compromised:
                    fig.add_trace(go.Scatter(
                        x=[df['date'].iloc[-1]], y=[5.0],
                        mode='markers',
                        marker=dict(color='red', size=15, symbol='x'),
                        name="ALERT"
                    ))
                
                fig.update_layout(
                    template="plotly_dark",
                    height=400,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("### 🛰️ NDTI FORECAST DATA TABLE")
                forecast_ndti_df = pd.DataFrame({
                    "Date": future_dates,
                    "Predicted NDTI": [round(x, 4) for x in preds_ndti],
                    "Risk Level": ["High" if x > 0.2 else "Low" for x in preds_ndti]
                })
                styled_ndti = style_risk_column(forecast_ndti_df, "Risk Level")
                st.dataframe(styled_ndti, use_container_width=True, hide_index=True)

                st.markdown("### 💧 NDWI FORECAST DATA TABLE")
                forecast_ndwi_df = pd.DataFrame({
                    "Date": future_dates,
                    "Predicted NDWI": [round(x, 4) for x in preds_ndwi],
                    "Risk Level": ["High" if x < 0.0 else "Low" for x in preds_ndwi]
                })
                styled_ndwi = style_risk_column(forecast_ndwi_df, "Risk Level")
                st.dataframe(styled_ndwi, use_container_width=True, hide_index=True)

        # =================================================
        # TAB 3 — INTELLIGENCE
        # =================================================
        with tab3:
            st.markdown('<div class="section-header">INTELLIGENCE REPORT</div>', unsafe_allow_html=True)
            st.info("System uses Sentinel-2 Optical Imagery and CHIRPS Precipitation data to monitor dams in Algeria.")
