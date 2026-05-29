import math
import pandas as pd
import folium

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter


EXCEL_FILE = "Database.xlsx"
OUTPUT_FILE = "map.html"

ADDRESS_COLUMN = "Адрес"
TOPIC_COLUMN = "Тема"
DESCRIPTION_COLUMN = "Описание"

LAT_COLUMN = "Latitude"
LON_COLUMN = "Longitude"


YEAR_COLORS = [
    "blue",
    "red",
    "green",
    "purple",
    "orange",
    "darkred",
    "cadetblue",
    "darkgreen",
    "pink",
    "black",
]


def is_valid_coord(value):
    try:
        value = float(value)
        return not math.isnan(value)
    except Exception:
        return False


def clean_value(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def geocode_address(address, geocode):
    search_queries = [
        f"{address}, Chicago, IL, USA",
        f"{address}, Cook County, IL, USA",
        f"{address}, DuPage County, IL, USA",
        f"{address}, Lake County, IL, USA",
        f"{address}, Will County, IL, USA",
        f"{address}, Kane County, IL, USA",
        f"{address}, McHenry County, IL, USA",
        f"{address}, Illinois, USA",
        f"{address}, USA",
    ]

    for query in search_queries:
        print(f"Пробую: {query}")
        location = geocode(query)

        if location:
            return location.latitude, location.longitude, query

    return None, None, None


geolocator = Nominatim(
    user_agent="chicago_year_layers_map",
    timeout=10
)

geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1.1,
    max_retries=2,
    error_wait_seconds=2
)


sheets = pd.read_excel(EXCEL_FILE, sheet_name=None)

all_points = []
updated_sheets = {}

for sheet_name, df in sheets.items():
    year = str(sheet_name).strip()

    print(f"\n=== Год / лист: {year} ===")

    df.columns = df.columns.str.strip()

    if ADDRESS_COLUMN not in df.columns:
        print(f"Пропускаю лист '{year}': нет столбца '{ADDRESS_COLUMN}'")
        updated_sheets[sheet_name] = df
        continue

    if TOPIC_COLUMN not in df.columns:
        df[TOPIC_COLUMN] = ""

    if DESCRIPTION_COLUMN not in df.columns:
        df[DESCRIPTION_COLUMN] = ""

    if LAT_COLUMN not in df.columns:
        df[LAT_COLUMN] = None

    if LON_COLUMN not in df.columns:
        df[LON_COLUMN] = None

    for idx, row in df.iterrows():
        address = clean_value(row[ADDRESS_COLUMN])

        if not address:
            print(f"Пропуск строки {idx + 2}: пустой адрес")
            continue

        lat = row[LAT_COLUMN]
        lon = row[LON_COLUMN]

        if is_valid_coord(lat) and is_valid_coord(lon):
            lat = float(lat)
            lon = float(lon)
            print(f"CACHED: {address} -> {lat}, {lon}")

        else:
            lat, lon, used_query = geocode_address(address, geocode)

            if lat is None or lon is None:
                print(f"FAILED: {address}")
                continue

            df.at[idx, LAT_COLUMN] = lat
            df.at[idx, LON_COLUMN] = lon

            print(f"OK: {address} -> {lat}, {lon} | query: {used_query}")

        all_points.append({
            "year": year,
            "sheet_name": sheet_name,
            "idx": idx,
            "address": address,
            "lat": lat,
            "lon": lon,
        })

    updated_sheets[sheet_name] = df


with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
    for sheet_name, df in updated_sheets.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)

print(f"\nКоординаты сохранены в {EXCEL_FILE}")


if not all_points:
    print("Нет найденных координат")
    exit()


avg_lat = sum(p["lat"] for p in all_points) / len(all_points)
avg_lon = sum(p["lon"] for p in all_points) / len(all_points)

m = folium.Map(
    location=[avg_lat, avg_lon],
    zoom_start=9,
    tiles="CartoDB positron",
    control_scale=True
)


for layer_index, (sheet_name, df) in enumerate(updated_sheets.items()):
    year = str(sheet_name).strip()
    color = YEAR_COLORS[layer_index % len(YEAR_COLORS)]

    layer = folium.FeatureGroup(
        name=f"{year}",
        show=True
    )

    year_points = [
        p for p in all_points
        if p["sheet_name"] == sheet_name
    ]

    for point in year_points:
        row = df.loc[point["idx"]]

        topic = clean_value(row[TOPIC_COLUMN]) or "Без темы"
        description = clean_value(row[DESCRIPTION_COLUMN])
        address = point["address"]

        popup_html = f"""
        <b>{topic}</b><br><br>
        {description}<br><br>
        <i>{address}</i><br>
        <small>Год: {year}</small>
        """

        folium.CircleMarker(
            location=[point["lat"], point["lon"]],
            radius=7,
            popup=folium.Popup(popup_html, max_width=400),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9
        ).add_to(layer)

    layer.add_to(m)


bounds = [[p["lat"], p["lon"]] for p in all_points]
m.fit_bounds(bounds, padding=(30, 30))

folium.LayerControl(collapsed=False).add_to(m)

m.save(OUTPUT_FILE)

print(f"Карта сохранена: {OUTPUT_FILE}")
print(f"Всего точек на карте: {len(all_points)}")
print(f"Количество слоев / годов: {len(updated_sheets)}")
