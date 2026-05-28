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


df = pd.read_excel(EXCEL_FILE)

# Убираем лишние пробелы в названиях колонок
df.columns = df.columns.str.strip()

if ADDRESS_COLUMN not in df.columns:
    raise ValueError(f"Нет столбца '{ADDRESS_COLUMN}'. Есть только: {list(df.columns)}")

if TOPIC_COLUMN not in df.columns:
    df[TOPIC_COLUMN] = ""

if DESCRIPTION_COLUMN not in df.columns:
    df[DESCRIPTION_COLUMN] = ""

if LAT_COLUMN not in df.columns:
    df[LAT_COLUMN] = None

if LON_COLUMN not in df.columns:
    df[LON_COLUMN] = None


geolocator = Nominatim(
    user_agent="chicago_address_map",
    timeout=10
)

geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1.1,
    max_retries=2,
    error_wait_seconds=2
)


coords = []

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
        location = None
        used_query = None

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
                used_query = query
                break

        if not location:
            print(f"FAILED: {address}")
            continue

        lat = location.latitude
        lon = location.longitude

        df.at[idx, LAT_COLUMN] = lat
        df.at[idx, LON_COLUMN] = lon

        print(f"OK: {address} -> {lat}, {lon} | query: {used_query}")

    coords.append((idx, address, lat, lon))


df.to_excel(EXCEL_FILE, index=False)
print(f"Координаты сохранены в {EXCEL_FILE}")


if not coords:
    print("Нет найденных координат")
    exit()


avg_lat = sum(lat for _, _, lat, _ in coords) / len(coords)
avg_lon = sum(lon for _, _, _, lon in coords) / len(coords)

m = folium.Map(
    location=[avg_lat, avg_lon],
    zoom_start=9,
    tiles="CartoDB positron",
    control_scale=True
)


for idx, address, lat, lon in coords:
    row = df.loc[idx]

    topic = clean_value(row[TOPIC_COLUMN])
    description = clean_value(row[DESCRIPTION_COLUMN])

    if not topic:
        topic = "Без темы"

    popup_html = f"""
    <b>{topic}</b><br><br>
    {description}<br><br>
    <i>{address}</i>
    """

    folium.CircleMarker(
        location=[lat, lon],
        radius=7,
        popup=folium.Popup(popup_html, max_width=400),
        color="blue",
        fill=True,
        fill_color="blue",
        fill_opacity=0.9
    ).add_to(m)


bounds = [[lat, lon] for _, _, lat, lon in coords]
m.fit_bounds(bounds, padding=(30, 30))

m.save(OUTPUT_FILE)

print(f"Карта сохранена: {OUTPUT_FILE}")
print(f"Точек на карте: {len(coords)}")
