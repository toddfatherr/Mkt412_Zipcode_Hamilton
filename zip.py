import streamlit as st
import folium
import requests
from streamlit_folium import st_folium

st.set_page_config(page_title="Cincinnati ZIP Map", layout="wide")

ALL_ZIPS = [
    "45202", "45203", "45204", "45205", "45206", "45207", "45208", "45209",
    "45211", "45212", "45213", "45214", "45215", "45216", "45217", "45218",
    "45219", "45220", "45223", "45224", "45225", "45226", "45227", "45229",
    "45230", "45231", "45232", "45233", "45236", "45237", "45238", "45239",
    "45240", "45241", "45242", "45243", "45244", "45245", "45246", "45247",
    "45248", "45249", "45251", "45252", "45255"
]

DEFAULT_HIGHLIGHTED = [
    "45202", "45208", "45215", "45227", "45230", "45236", "45241",
    "45242", "45244", "45245", "45247", "45248", "45251", "45255"
]

MAP_STYLES = {
    "Clean Light": "CartoDB Positron",
    "Standard Map": "OpenStreetMap",
    "Dark Map": "CartoDB dark_matter"
}

if "highlighted" not in st.session_state:
    st.session_state.highlighted = DEFAULT_HIGHLIGHTED.copy()

st.title("Cincinnati ZIP Target Market Map")
st.caption("Choose which ZIP codes are in your target market.")

# -----------------------------
# SIDEBAR
# -----------------------------
st.sidebar.header("Map Controls")

map_style_name = st.sidebar.selectbox(
    "Map Style",
    options=list(MAP_STYLES.keys()),
    index=0
)

highlight_color = st.sidebar.color_picker("Target Market Color", "#D9EF6B")
show_labels = st.sidebar.checkbox("Show ZIP labels", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("Quick Actions")

col1, col2 = st.sidebar.columns(2)
if col1.button("Select All"):
    st.session_state.highlighted = ALL_ZIPS.copy()
if col2.button("Clear All"):
    st.session_state.highlighted = []

col3, col4 = st.sidebar.columns(2)
if col3.button("Reset Default"):
    st.session_state.highlighted = DEFAULT_HIGHLIGHTED.copy()
if col4.button("Sort ZIPs"):
    st.session_state.highlighted = sorted(st.session_state.highlighted)

st.sidebar.markdown("---")
st.sidebar.subheader("Paste ZIPs")

zip_text = st.sidebar.text_area(
    "Paste comma-separated ZIPs",
    placeholder="45202, 45208, 45215"
)

if st.sidebar.button("Apply Pasted ZIPs"):
    pasted = [z.strip() for z in zip_text.replace("\n", ",").split(",")]
    pasted = [z for z in pasted if z in ALL_ZIPS]
    st.session_state.highlighted = pasted

highlighted = st.sidebar.multiselect(
    "Target Market ZIPs",
    options=ALL_ZIPS,
    default=st.session_state.highlighted
)

st.session_state.highlighted = highlighted

st.sidebar.markdown("---")
st.sidebar.metric("Target Market ZIP Count", len(highlighted))

if highlighted:
    st.sidebar.write("Selected ZIPs:")
    st.sidebar.write(", ".join(highlighted))

# -----------------------------
# LOAD ZIP BOUNDARIES
# -----------------------------
URL = "https://raw.githubusercontent.com/OpenDataDE/State-zip-code-GeoJSON/master/oh_ohio_zip_codes_geo.min.json"
geo = requests.get(URL, timeout=30).json()

features = []
for f in geo["features"]:
    zip_code = f["properties"]["ZCTA5CE10"]
    if zip_code in ALL_ZIPS:
        f["properties"]["ZIP_DISPLAY"] = zip_code
        features.append(f)

filtered_geo = {
    "type": "FeatureCollection",
    "features": features
}

# -----------------------------
# BUILD MAP
# -----------------------------
m = folium.Map(
    location=[39.1031, -84.5120],
    zoom_start=10,
    tiles=MAP_STYLES[map_style_name]
)

def style(feature):
    z = feature["properties"]["ZIP_DISPLAY"]

    if z in highlighted:
        return {
            "fillColor": highlight_color,
            "color": "#111111",
            "weight": 1.4,
            "fillOpacity": 0.58
        }
    else:
        return {
            "fillColor": "#000000",
            "color": "#9A9A9A",
            "weight": 0.8,
            "fillOpacity": 0
        }

def highlight_function(feature):
    z = feature["properties"]["ZIP_DISPLAY"]

    if z in highlighted:
        return {
            "color": "#000000",
            "weight": 2.0,
            "fillOpacity": 0.68
        }
    else:
        return {
            "color": "#555555",
            "weight": 1.3,
            "fillOpacity": 0.05
        }

tooltip = None
if show_labels:
    tooltip = folium.GeoJsonTooltip(
        fields=["ZIP_DISPLAY"],
        aliases=["ZIP:"],
        sticky=False,
        labels=True
    )

geojson_layer = folium.GeoJson(
    filtered_geo,
    style_function=style,
    highlight_function=highlight_function,
    tooltip=tooltip,
    name="ZIP Codes"
)
geojson_layer.add_to(m)

try:
    bounds = geojson_layer.get_bounds()
    if bounds:
        m.fit_bounds(bounds, padding=(10, 10))
except Exception:
    pass

# -----------------------------
# LEGEND
# -----------------------------
legend_html = f"""
<div style="
    position: fixed;
    bottom: 35px;
    left: 35px;
    width: 240px;
    background-color: rgba(255,255,255,0.92);
    border: 1px solid #CFCFCF;
    border-radius: 10px;
    z-index: 9999;
    font-size: 14px;
    color: #222;
    padding: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
">
    <b>Cincinnati ZIP Map</b><br><br>
    <span style="
        display:inline-block;
        width:14px;
        height:14px;
        background:{highlight_color};
        border:1.4px solid #111111;
        margin-right:8px;
        vertical-align:middle;
    "></span> Target Market ZIPs<br><br>
    <span style="
        display:inline-block;
        width:14px;
        height:14px;
        background:transparent;
        border:1px solid #9A9A9A;
        margin-right:8px;
        vertical-align:middle;
    "></span> Other ZIPs
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# -----------------------------
# DISPLAY MAP
# -----------------------------
st_folium(m, width=1400, height=800)

# -----------------------------
# BOTTOM SUMMARY
# -----------------------------
st.markdown("### Target Market ZIPs")
if highlighted:
    st.write(", ".join(highlighted))
else:
    st.write("No ZIPs selected.")
