import streamlit as st
import folium
import requests
import pandas as pd
from streamlit_folium import st_folium
from branca.element import Template, MacroElement

st.set_page_config(page_title="Cincinnati ZIP Market Map", layout="wide")

# ---------------------------------------------------
# CONSTANTS
# ---------------------------------------------------
CSV_FILE = "Client project demo data 03-02-26.csv"

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

AGE_BINS = [
    "<5", "5--9", "10--14", "15-19", "20-24", "25-29", "30-34", "35-39",
    "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79",
    "80-84", "85+"
]

MAP_STYLES = {
    "Clean Light": "CartoDB Positron",
    "Standard Map": "OpenStreetMap",
    "Dark Map": "CartoDB dark_matter"
}

CLASS_COLORS = {
    "Primary Target": "#2ca25f",
    "Secondary Opportunity": "#f1c40f",
    "Partial Fit": "#74add1",
    "Low Fit": "#d9d9d9"
}

if "manual_selected" not in st.session_state:
    st.session_state.manual_selected = DEFAULT_HIGHLIGHTED.copy()

# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------
def clean_currency(x):
    if pd.isna(x):
        return 0.0
    return float(str(x).replace("$", "").replace(",", "").strip() or 0)

def clean_numeric(x):
    if pd.isna(x):
        return 0.0
    return float(str(x).replace(",", "").strip() or 0)

def clean_zip(x):
    if pd.isna(x):
        return None
    s = str(x).strip()
    if not s:
        return None
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(5)

@st.cache_data
def load_demographics(csv_file):
    df = pd.read_csv(csv_file)
    df.columns = [str(c).strip() for c in df.columns]

    required_cols = ["Zip", "Income", "% bachelors degree", "Families", "Gender"]
    for col in required_cols + AGE_BINS:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df["Zip"] = df["Zip"].replace("", pd.NA).ffill()
    df["Income"] = df["Income"].replace("", pd.NA).ffill()
    df["% bachelors degree"] = df["% bachelors degree"].replace("", pd.NA).ffill()
    df["Families"] = df["Families"].replace("", pd.NA).ffill()

    df["Zip"] = df["Zip"].apply(clean_zip)
    df["Gender"] = df["Gender"].astype(str).str.strip().str.title()
    df = df[df["Zip"].isin(ALL_ZIPS)].copy()
    df = df[df["Gender"].isin(["Male", "Female", "Total"])].copy()

    df["Income"] = df["Income"].apply(clean_currency)
    df["% bachelors degree"] = df["% bachelors degree"].apply(clean_numeric)
    df["Families"] = df["Families"].apply(clean_numeric)

    extra_numeric = [
        "Male", "Female", "Total",
        "Income-Cutoff", "Education-Cutoff", "Families-Cutoff",
        "Multi-Criteria Cutoff", "Sample per zip"
    ]
    for col in AGE_BINS + [c for c in extra_numeric if c in df.columns]:
        df[col] = df[col].apply(clean_numeric)

    zip_level = (
        df.groupby("Zip", as_index=False)[["Income", "% bachelors degree", "Families"]]
        .max()
        .rename(columns={
            "Income": "income",
            "% bachelors degree": "bachelors_pct",
            "Families": "families"
        })
    )

    gender_rows = df[df["Gender"].isin(["Male", "Female"])].copy()
    melted = gender_rows.melt(
        id_vars=["Zip", "Gender"],
        value_vars=AGE_BINS,
        var_name="age_bin",
        value_name="count"
    )

    melted["col_name"] = (
        melted["Gender"].str.lower()
        + "_"
        + melted["age_bin"]
            .str.replace("+", "_plus", regex=False)
            .str.replace("<", "lt_", regex=False)
            .str.replace("-", "_", regex=False)
    )

    wide_age = (
        melted.pivot_table(
            index="Zip",
            columns="col_name",
            values="count",
            aggfunc="sum",
            fill_value=0
        )
        .reset_index()
    )

    merged = zip_level.merge(wide_age, on="Zip", how="left").fillna(0)

    male_cols = [c for c in merged.columns if c.startswith("male_")]
    female_cols = [c for c in merged.columns if c.startswith("female_")]

    merged["male_total_calc"] = merged[male_cols].sum(axis=1)
    merged["female_total_calc"] = merged[female_cols].sum(axis=1)
    merged["total_pop_calc"] = merged["male_total_calc"] + merged["female_total_calc"]

    return merged.sort_values("Zip").reset_index(drop=True)

def selected_demo_count(row, selected_age_bins, gender_choice):
    total = 0
    for age in selected_age_bins:
        safe_age = age.replace("+", "_plus").replace("<", "lt_").replace("-", "_")
        if gender_choice in ["Female", "Both"]:
            total += row.get(f"female_{safe_age}", 0)
        if gender_choice in ["Male", "Both"]:
            total += row.get(f"male_{safe_age}", 0)
    return total

def score_market(row):
    fam = bool(row["families_above_mean"])
    inc = bool(row["income_above_mean"])
    edu = bool(row["education_above_mean"])

    # 3 = families AND (income OR education)
    if fam and (inc or edu):
        return 3, "Primary Target"

    # 2 = income AND education, but NOT families
    if (not fam) and inc and edu:
        return 2, "Secondary Opportunity"

    # 1 = family only
    # 1 = income only
    # 1 = education only
    # 1 = family + nothing else
    if fam or inc or edu:
        return 1, "Partial Fit"

    # 0 = none
    return 0, "Low Fit"

def add_leaflet_control(map_obj, html_content, position="bottomleft"):
    template = f"""
    {{% macro script(this, kwargs) %}}
    var control = L.control({{position: '{position}'}});

    control.onAdd = function(map) {{
        var div = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
        div.innerHTML = `{html_content}`;
        div.style.background = 'transparent';
        div.style.border = 'none';
        div.style.boxShadow = 'none';
        return div;
    }};

    control.addTo({{{{this._parent.get_name()}}}});
    {{% endmacro %}}
    """
    macro = MacroElement()
    macro._template = Template(template)
    map_obj.get_root().add_child(macro)

# ---------------------------------------------------
# TITLE
# ---------------------------------------------------
st.title("Cincinnati ZIP Market Map")
st.caption("Switch between manual ZIP selection and a built-in data-driven target market map.")

# ---------------------------------------------------
# SIDEBAR
# ---------------------------------------------------
st.sidebar.header("Controls")

view_mode = st.sidebar.radio(
    "Map Mode",
    ["Manual Highlight Mode", "Data-Driven Market Mode"],
    index=0
)

map_style_name = st.sidebar.selectbox(
    "Map Style",
    options=list(MAP_STYLES.keys()),
    index=0
)

show_labels = st.sidebar.checkbox("Show ZIP labels", value=True)

if view_mode == "Manual Highlight Mode":
    st.sidebar.subheader("Manual ZIP Selection")

    manual_color = st.sidebar.color_picker("Target Market Color", "#D9EF6B")

    c1, c2 = st.sidebar.columns(2)
    if c1.button("Select All"):
        st.session_state.manual_selected = ALL_ZIPS.copy()
    if c2.button("Clear All"):
        st.session_state.manual_selected = []

    c3, c4 = st.sidebar.columns(2)
    if c3.button("Reset Default"):
        st.session_state.manual_selected = DEFAULT_HIGHLIGHTED.copy()
    if c4.button("Sort ZIPs"):
        st.session_state.manual_selected = sorted(st.session_state.manual_selected)

    pasted = st.sidebar.text_area(
        "Paste comma-separated ZIPs",
        placeholder="45202, 45208, 45230"
    )

    if st.sidebar.button("Apply Pasted ZIPs"):
        zips = [z.strip() for z in pasted.replace("\n", ",").split(",")]
        zips = [z for z in zips if z in ALL_ZIPS]
        st.session_state.manual_selected = zips

    manual_selected = st.sidebar.multiselect(
        "Target Market ZIPs",
        options=ALL_ZIPS,
        default=st.session_state.manual_selected
    )
    st.session_state.manual_selected = manual_selected
    st.sidebar.metric("Selected ZIP count", len(manual_selected))

else:
    st.sidebar.subheader("Data-Driven Targeting")

    gender_choice = st.sidebar.radio(
        "Gender",
        ["Female", "Male", "Both"],
        index=0
    )

    selected_age_bins = st.sidebar.multiselect(
        "Age Ranges",
        options=AGE_BINS,
        default=["25-29", "30-34", "35-39", "40-44"]
    )

    show_low_fit = st.sidebar.checkbox("Show low-fit ZIPs", value=True)
    show_ranked_table = st.sidebar.checkbox("Show ranked summary table", value=True)
    show_detail_table = st.sidebar.checkbox("Show detailed age/gender table", value=False)

# ---------------------------------------------------
# LOAD DEMOGRAPHICS
# ---------------------------------------------------
try:
    df_demo = load_demographics(CSV_FILE)
except Exception as e:
    st.error(f"Could not load {CSV_FILE}: {e}")
    st.stop()

zip_lookup = {}

if view_mode == "Data-Driven Market Mode":
    if not selected_age_bins:
        st.warning("Choose at least one age range.")
        st.stop()

    df_demo["target_demo_count"] = df_demo.apply(
        lambda r: selected_demo_count(r, selected_age_bins, gender_choice),
        axis=1
    )

    income_mean = df_demo["income"].mean()
    bachelors_mean = df_demo["bachelors_pct"].mean()
    families_mean = df_demo["families"].mean()

    df_demo["income_above_mean"] = df_demo["income"] > income_mean
    df_demo["education_above_mean"] = df_demo["bachelors_pct"] > bachelors_mean
    df_demo["families_above_mean"] = df_demo["families"] > families_mean

    score_results = df_demo.apply(score_market, axis=1)
    df_demo["market_score"] = [x[0] for x in score_results]
    df_demo["market_class"] = [x[1] for x in score_results]

    zip_lookup = df_demo.set_index("Zip").to_dict(orient="index")

    total_market = int(df_demo["target_demo_count"].sum())
    primary_total = int(
        df_demo.loc[df_demo["market_class"] == "Primary Target", "target_demo_count"].sum()
    )
    secondary_total = int(
        df_demo.loc[df_demo["market_class"] == "Secondary Opportunity", "target_demo_count"].sum()
    )
else:
    total_market = primary_total = secondary_total = None

# ---------------------------------------------------
# PAGE SUMMARY ABOVE MAP
# ---------------------------------------------------
if view_mode == "Data-Driven Market Mode":
    st.markdown("### Target Market Size")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Regional Market", f"{total_market:,}")
    c2.metric("Primary Target ZIPs", f"{primary_total:,}")
    c3.metric("Secondary Target ZIPs", f"{secondary_total:,}")

# ---------------------------------------------------
# LOAD GEOJSON
# ---------------------------------------------------
URL = "https://raw.githubusercontent.com/OpenDataDE/State-zip-code-GeoJSON/master/oh_ohio_zip_codes_geo.min.json"
geo = requests.get(URL, timeout=30).json()

features = []
for f in geo["features"]:
    zip_code = f["properties"]["ZCTA5CE10"]
    if zip_code in ALL_ZIPS:
        f["properties"]["ZIP_DISPLAY"] = zip_code

        if view_mode == "Data-Driven Market Mode" and zip_code in zip_lookup:
            row = zip_lookup[zip_code]
            f["properties"]["income_fmt"] = f"${row['income']:,.0f}"
            f["properties"]["bachelors_fmt"] = f"{row['bachelors_pct']:.2f}%"
            f["properties"]["families_fmt"] = f"{row['families']:,.0f}"
            f["properties"]["target_demo_fmt"] = f"{row['target_demo_count']:,.0f}"
            f["properties"]["class_label"] = row["market_class"]
            f["properties"]["score_fmt"] = f"{int(row['market_score'])}"
            f["properties"]["female_total_fmt"] = f"{row['female_total_calc']:,.0f}"
            f["properties"]["male_total_fmt"] = f"{row['male_total_calc']:,.0f}"
            f["properties"]["income_above_fmt"] = "Yes" if row["income_above_mean"] else "No"
            f["properties"]["education_above_fmt"] = "Yes" if row["education_above_mean"] else "No"
            f["properties"]["families_above_fmt"] = "Yes" if row["families_above_mean"] else "No"

        features.append(f)

filtered_geo = {"type": "FeatureCollection", "features": features}

# ---------------------------------------------------
# MAP
# ---------------------------------------------------
m = folium.Map(
    location=[39.1031, -84.5120],
    zoom_start=10,
    tiles=MAP_STYLES[map_style_name]
)

def manual_style(feature):
    z = feature["properties"]["ZIP_DISPLAY"]
    if z in st.session_state.manual_selected:
        return {
            "fillColor": manual_color,
            "color": "#111111",
            "weight": 1.3,
            "fillOpacity": 0.58
        }
    return {
        "fillColor": "#000000",
        "color": "#9A9A9A",
        "weight": 0.8,
        "fillOpacity": 0
    }

def manual_highlight(feature):
    z = feature["properties"]["ZIP_DISPLAY"]
    if z in st.session_state.manual_selected:
        return {
            "color": "#000000",
            "weight": 1.8,
            "fillOpacity": 0.68
        }
    return {
        "color": "#555555",
        "weight": 1.2,
        "fillOpacity": 0.05
    }

def data_style(feature):
    z = feature["properties"]["ZIP_DISPLAY"]
    row = zip_lookup.get(z)

    if row is None:
        return {"fillColor": "#000000", "color": "#BBBBBB", "weight": 0.7, "fillOpacity": 0}

    market_class = row["market_class"]

    if market_class == "Low Fit" and not show_low_fit:
        return {"fillColor": "#000000", "color": "#CFCFCF", "weight": 0.6, "fillOpacity": 0}

    fill_color = CLASS_COLORS[market_class]

    if market_class == "Primary Target":
        return {"fillColor": fill_color, "color": "#111111", "weight": 1.3, "fillOpacity": 0.65}
    elif market_class == "Secondary Opportunity":
        return {"fillColor": fill_color, "color": "#111111", "weight": 1.1, "fillOpacity": 0.58}
    elif market_class == "Partial Fit":
        return {"fillColor": fill_color, "color": "#888888", "weight": 0.9, "fillOpacity": 0.35}
    else:
        return {"fillColor": fill_color, "color": "#BBBBBB", "weight": 0.7, "fillOpacity": 0.15 if show_low_fit else 0}

def data_highlight(feature):
    z = feature["properties"]["ZIP_DISPLAY"]
    row = zip_lookup.get(z)
    if row is None:
        return {"color": "#666666", "weight": 1.2, "fillOpacity": 0.1}

    if row["market_class"] in ["Primary Target", "Secondary Opportunity"]:
        return {"color": "#000000", "weight": 1.8, "fillOpacity": 0.75}
    return {"color": "#666666", "weight": 1.2, "fillOpacity": 0.25}

if view_mode == "Manual Highlight Mode":
    tooltip = folium.GeoJsonTooltip(
        fields=["ZIP_DISPLAY"],
        aliases=["ZIP:"],
        sticky=False,
        labels=True
    ) if show_labels else None

    geojson_layer = folium.GeoJson(
        filtered_geo,
        style_function=manual_style,
        highlight_function=manual_highlight,
        tooltip=tooltip,
        name="ZIP Codes"
    )
else:
    tooltip = folium.GeoJsonTooltip(
        fields=["ZIP_DISPLAY", "class_label", "target_demo_fmt"],
        aliases=["ZIP:", "Class:", "Target demographic count:"],
        sticky=False,
        labels=True
    ) if show_labels else None

    popup = folium.GeoJsonPopup(
        fields=[
            "ZIP_DISPLAY",
            "class_label",
            "score_fmt",
            "target_demo_fmt",
            "income_fmt",
            "bachelors_fmt",
            "families_fmt",
            "families_above_fmt",
            "income_above_fmt",
            "education_above_fmt",
            "female_total_fmt",
            "male_total_fmt"
        ],
        aliases=[
            "ZIP:",
            "Market class:",
            "Score:",
            "Target demographic count:",
            "Income:",
            "% Bachelor's Degree:",
            "Families:",
            "Families above mean:",
            "Income above mean:",
            "Education above mean:",
            "Female total:",
            "Male total:"
        ],
        labels=True,
        localize=True
    )

    geojson_layer = folium.GeoJson(
        filtered_geo,
        style_function=data_style,
        highlight_function=data_highlight,
        tooltip=tooltip,
        popup=popup,
        name="ZIP Codes"
    )

geojson_layer.add_to(m)

try:
    bounds = geojson_layer.get_bounds()
    if bounds:
        m.fit_bounds(bounds, padding=(10, 10))
except Exception:
    pass

# ---------------------------------------------------
# LEGEND
# ---------------------------------------------------
if view_mode == "Manual Highlight Mode":
    legend_box = f"""
    <div style="
        background-color: rgba(255,255,255,0.94);
        border: 1px solid #CFCFCF;
        border-radius: 10px;
        padding: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        font-size: 14px;
        color: #222;
        line-height: 1.6;
        min-width: 220px;
    ">
        <b>Cincinnati ZIP Map</b><br><br>
        <span style="
            display:inline-block;
            width:14px;
            height:14px;
            background:{manual_color};
            border:1.2px solid #111111;
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
    add_leaflet_control(m, legend_box, position="bottomleft")

else:
    legend_box = f"""
    <div style="
        background-color: rgba(255,255,255,0.94);
        border: 1px solid #CFCFCF;
        border-radius: 10px;
        padding: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        font-size: 14px;
        color: #222;
        line-height: 1.6;
        min-width: 250px;
    ">
        <b>Data-Driven Target Market</b><br><br>

        <span style="
            display:inline-block;
            width:14px;
            height:14px;
            background:{CLASS_COLORS['Primary Target']};
            border:1.2px solid #111111;
            margin-right:8px;
            vertical-align:middle;
        "></span> Primary Target<br><br>

        <span style="
            display:inline-block;
            width:14px;
            height:14px;
            background:{CLASS_COLORS['Secondary Opportunity']};
            border:1.2px solid #111111;
            margin-right:8px;
            vertical-align:middle;
        "></span> Secondary Opportunity<br><br>

        <span style="
            display:inline-block;
            width:14px;
            height:14px;
            background:{CLASS_COLORS['Partial Fit']};
            border:1px solid #888888;
            margin-right:8px;
            vertical-align:middle;
        "></span> Partial Fit<br><br>

        <span style="
            display:inline-block;
            width:14px;
            height:14px;
            background:{CLASS_COLORS['Low Fit']};
            border:1px solid #BBBBBB;
            margin-right:8px;
            vertical-align:middle;
        "></span> Low Fit
    </div>
    """
    add_leaflet_control(m, legend_box, position="bottomleft")

# ---------------------------------------------------
# DISPLAY MAP
# ---------------------------------------------------
st_folium(m, width=1400, height=800)

# ---------------------------------------------------
# BOTTOM OUTPUT
# ---------------------------------------------------
if view_mode == "Manual Highlight Mode":
    st.markdown("### Target Market ZIPs")
    if st.session_state.manual_selected:
        st.write(", ".join(st.session_state.manual_selected))
    else:
        st.write("No ZIPs selected.")
else:
    st.markdown("### Data-Driven Summary")

    st.write(
        f"**Current target market:** {gender_choice} | "
        f"Age bins: {', '.join(selected_age_bins)}"
    )

    st.write(
        f"**Benchmarks used:** "
        f"Income mean = ${income_mean:,.0f}, "
        f"% Bachelor's Degree mean = {bachelors_mean:.2f}%, "
        f"Families mean = {families_mean:,.0f}"
    )

    st.write(
        "**Scoring logic:** "
        "3 = families above mean and income or education above mean; "
        "2 = income and education above mean but not families; "
        "1 = family only or income only or education only; "
        "0 = none."
    )

    summary_cols = [
        "Zip", "market_class", "market_score", "target_demo_count", "income",
        "bachelors_pct", "families", "families_above_mean",
        "income_above_mean", "education_above_mean"
    ]

    df_summary = df_demo[summary_cols].copy().rename(columns={
        "Zip": "ZIP",
        "market_class": "Market Class",
        "market_score": "Score",
        "target_demo_count": "Target Demographic Count",
        "income": "Income",
        "bachelors_pct": "% Bachelor's Degree",
        "families": "Families",
        "families_above_mean": "Families Above Mean",
        "income_above_mean": "Income Above Mean",
        "education_above_mean": "Education Above Mean"
    })

    df_summary = df_summary.sort_values(
        by=["Score", "Target Demographic Count", "Income"],
        ascending=[False, False, False]
    ).reset_index(drop=True)

    if show_ranked_table:
        st.dataframe(df_summary, use_container_width=True)

    if show_detail_table:
        st.markdown("### Detailed Age / Gender Population Table")

        detail_cols = ["Zip", "income", "bachelors_pct", "families"]
        for gender in ["female", "male"]:
            for age in AGE_BINS:
                safe_age = age.replace("+", "_plus").replace("<", "lt_").replace("-", "_")
                detail_cols.append(f"{gender}_{safe_age}")

        df_detail = df_demo[detail_cols].copy().rename(columns={
            "Zip": "ZIP",
            "income": "Income",
            "bachelors_pct": "% Bachelor's Degree",
            "families": "Families"
        })

        st.dataframe(df_detail, use_container_width=True)


