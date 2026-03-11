import streamlit as st
import folium
import requests
from streamlit_folium import st_folium

st.set_page_config(page_title="Cincinnati ZIP Map", layout="wide")

ALL_ZIPS = [
"45202","45203","45204","45205","45206","45207","45208","45209",
"45211","45212","45213","45214","45215","45216","45217","45218",
"45219","45220","45223","45224","45225","45226","45227","45229",
"45230","45231","45232","45233","45236","45237","45238","45239",
"45240","45241","45242","45243","45244","45245","45246","45247",
"45248","45249","45251","45252","45255"
]

DEFAULT_HIGHLIGHTED = [
"45202","45208","45215","45227","45230","45236","45241",
"45242","45244","45245","45247","45248","45251","45255"
]

st.sidebar.header("ZIP Controls")

highlighted = st.sidebar.multiselect(
"Highlighted ZIPs",
options=ALL_ZIPS,
default=DEFAULT_HIGHLIGHTED
)

highlight_color = st.sidebar.color_picker("Highlight Color","#00E5FF")

st.title("Cincinnati ZIP Highlight Map")

# Load ZIP boundaries from public dataset
URL = "https://raw.githubusercontent.com/OpenDataDE/State-zip-code-GeoJSON/master/oh_ohio_zip_codes_geo.min.json"

geo = requests.get(URL).json()

features = []

for f in geo["features"]:
    zip_code = f["properties"]["ZCTA5CE10"]
    if zip_code in ALL_ZIPS:
        f["properties"]["ZIP_DISPLAY"] = zip_code
        features.append(f)

filtered_geo = {
"type":"FeatureCollection",
"features":features
}

m = folium.Map(
location=[39.1031,-84.5120],
zoom_start=10,
tiles="CartoDB dark_matter"
)

def style(feature):

    z = feature["properties"]["ZIP_DISPLAY"]

    if z in highlighted:
        return {
        "fillColor":highlight_color,
        "color":"white",
        "weight":2,
        "fillOpacity":0.7
        }

    else:
        return {
        "fillColor":"#222222",
        "color":"white",
        "weight":1,
        "fillOpacity":0.1
        }

folium.GeoJson(
filtered_geo,
style_function=style,
tooltip=folium.GeoJsonTooltip(fields=["ZIP_DISPLAY"],aliases=["ZIP:"])
).add_to(m)

st_folium(m,width=1300,height=750)
