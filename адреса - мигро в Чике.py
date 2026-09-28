import math
import pandas as pd
import folium

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter


# =========================================================
# НАСТРОЙКИ
# =========================================================

EXCEL_FILE = "Database.xlsx"
OUTPUT_FILE = "map.html"

ADDRESS_COLUMN = "Адрес"
TOPIC_COLUMN = "Тема"
DESCRIPTION_COLUMN = "Описание"

LAT_COLUMN = "Latitude"
LON_COLUMN = "Longitude"


# Цвета по годам.
# Если появятся новые годы — им автоматически назначится цвет.
COLORS = [
    "#4361ee",  # blue
    "#e63946",  # red
    "#2a9d8f",  # green
    "#f4a261",  # orange
    "#8338ec",  # purple
    "#9b2226",  # dark red
    "#3a86ff",  # light blue
    "#588157",  # dark green
    "#ff006e",  # pink
    "#6c757d",  # gray
    "#fb8500",  # dark orange
    "#7209b7",  # dark purple
]


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

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

        try:
            location = geocode(query)
        except Exception as e:
            print(f"Ошибка геокодинга: {e}")
            continue

        if location:
            return (
                location.latitude,
                location.longitude,
                query
            )

    return None, None, None


# =========================================================
# GEOCODER
# =========================================================

geolocator = Nominatim(
    user_agent="chicago_migration_history_map",
    timeout=10
)

geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1.1,
    max_retries=2,
    error_wait_seconds=2
)


# =========================================================
# ЧИТАЕМ ВСЕ ЛИСТЫ EXCEL
# =========================================================

sheets = pd.read_excel(
    EXCEL_FILE,
    sheet_name=None
)

all_points = []
updated_sheets = {}


# =========================================================
# ОБРАБАТЫВАЕМ КАЖДЫЙ ГОД
# =========================================================

for sheet_name, df in sheets.items():

    year = str(sheet_name).strip()

    print()
    print("=" * 50)
    print(f"ГОД: {year}")
    print("=" * 50)

    df.columns = df.columns.str.strip()

    # Если на листе вообще нет адресов
    if ADDRESS_COLUMN not in df.columns:

        print(
            f"Пропускаю лист '{year}': "
            f"нет столбца '{ADDRESS_COLUMN}'"
        )

        updated_sheets[sheet_name] = df
        continue


    # Создаем недостающие столбцы

    if TOPIC_COLUMN not in df.columns:
        df[TOPIC_COLUMN] = ""

    if DESCRIPTION_COLUMN not in df.columns:
        df[DESCRIPTION_COLUMN] = ""

    if LAT_COLUMN not in df.columns:
        df[LAT_COLUMN] = None

    if LON_COLUMN not in df.columns:
        df[LON_COLUMN] = None


    # -----------------------------------------------------
    # ОБРАБАТЫВАЕМ ТОЧКИ
    # -----------------------------------------------------

    for idx, row in df.iterrows():

        address = clean_value(
            row[ADDRESS_COLUMN]
        )

        if not address:
            print(
                f"Пропуск строки {idx + 2}: "
                f"пустой адрес"
            )
            continue


        lat = row[LAT_COLUMN]
        lon = row[LON_COLUMN]


        # Уже есть координаты

        if (
            is_valid_coord(lat)
            and is_valid_coord(lon)
        ):

            lat = float(lat)
            lon = float(lon)

            print(
                f"CACHED: {address} "
                f"-> {lat}, {lon}"
            )


        # Нужно геокодировать

        else:

            lat, lon, used_query = geocode_address(
                address,
                geocode
            )

            if lat is None or lon is None:

                print(
                    f"FAILED: {address}"
                )

                continue


            # Записываем координаты обратно

            df.at[idx, LAT_COLUMN] = lat
            df.at[idx, LON_COLUMN] = lon


            print(
                f"OK: {address} "
                f"-> {lat}, {lon} "
                f"| query: {used_query}"
            )


        # Добавляем точку

        all_points.append({

            "year": year,
            "sheet_name": sheet_name,

            "idx": idx,

            "address": address,

            "lat": lat,
            "lon": lon
        })


    updated_sheets[sheet_name] = df


# =========================================================
# СОХРАНЯЕМ КООРДИНАТЫ В EXCEL
# =========================================================

with pd.ExcelWriter(
    EXCEL_FILE,
    engine="openpyxl"
) as writer:

    for sheet_name, df in updated_sheets.items():

        df.to_excel(
            writer,
            sheet_name=sheet_name,
            index=False
        )


print()
print(
    f"Координаты сохранены в {EXCEL_FILE}"
)


# =========================================================
# ЕСЛИ ТОЧЕК НЕТ
# =========================================================

if not all_points:

    print("Нет найденных координат")

    exit()


# =========================================================
# ЦЕНТР КАРТЫ
# =========================================================

avg_lat = sum(
    p["lat"] for p in all_points
) / len(all_points)

avg_lon = sum(
    p["lon"] for p in all_points
) / len(all_points)


# =========================================================
# СОЗДАЕМ КАРТУ
# =========================================================

m = folium.Map(
    location=[avg_lat, avg_lon],

    zoom_start=10,

    # ВАЖНО:
    # control=False убирает OpenStreetMap
    # из списка годов справа

    tiles=None,

    control_scale=True
)


# =========================================================
# ПОДЛОЖКА БЕЗ API KEY
# =========================================================

folium.TileLayer(
    tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",

    attr="© OpenStreetMap contributors",

    name="Map",

    overlay=False,

    control=False,

    max_zoom=19
).add_to(m)


# =========================================================
# СОЗДАЕМ СЛОИ ПО ГОДАМ
# =========================================================

for layer_index, (sheet_name, df) in enumerate(
    updated_sheets.items()
):

    year = str(sheet_name).strip()

    color = COLORS[
        layer_index % len(COLORS)
    ]


    layer = folium.FeatureGroup(
        name=year,
        show=True
    )


    year_points = [

        p for p in all_points

        if p["sheet_name"] == sheet_name
    ]


    for point in year_points:

        row = df.loc[
            point["idx"]
        ]


        topic = clean_value(
            row[TOPIC_COLUMN]
        )

        if not topic:
            topic = "Без темы"


        description = clean_value(
            row[DESCRIPTION_COLUMN]
        )


        address = point["address"]


        # -------------------------------------------------
        # POPUP
        # -------------------------------------------------

        popup_html = f"""
        <div style="
            font-family: Arial, sans-serif;
            width: 300px;
        ">

            <div style="
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 8px;
            ">
                {topic}
            </div>

            <div style="
                font-size: 14px;
                line-height: 1.4;
                margin-bottom: 12px;
            ">
                {description}
            </div>

            <div style="
                font-size: 12px;
                color: #666;
            ">
                {address}
            </div>

            <div style="
                margin-top: 8px;
                font-size: 12px;
                font-weight: bold;
                color: {color};
            ">
                {year}
            </div>

        </div>
        """


        # -------------------------------------------------
        # МАРКЕР
        # -------------------------------------------------

        folium.CircleMarker(

            location=[
                point["lat"],
                point["lon"]
            ],

            radius=7,

            popup=folium.Popup(
                popup_html,
                max_width=350
            ),

            tooltip=topic,

            color="white",

            weight=1,

            fill=True,

            fill_color=color,

            fill_opacity=0.95

        ).add_to(layer)


    layer.add_to(m)


# =========================================================
# АВТОМАТИЧЕСКИЙ ZOOM
# =========================================================

bounds = [

    [p["lat"], p["lon"]]

    for p in all_points
]

m.fit_bounds(
    bounds,
    padding=(40, 40)
)


# =========================================================
# ПЕРЕКЛЮЧАТЕЛЬ ГОДОВ
# =========================================================

folium.LayerControl(
    collapsed=False
).add_to(m)


# =========================================================
# ЗАГОЛОВОК
# =========================================================

title_html = """
<div style="
    position: fixed;
    top: 20px;
    left: 50px;
    z-index: 9999;

    background: rgba(255,255,255,0.92);

    padding: 12px 18px;

    border-radius: 8px;

    box-shadow:
        0 1px 5px rgba(0,0,0,0.25);

    font-family: Arial, sans-serif;
">

    <div style="
        font-size: 20px;
        font-weight: bold;
    ">
        Mapping Migration: Chicago
    </div>

    <div style="
        font-size: 12px;
        color: #666;
        margin-top: 3px;
    ">
        Historical Migration Map
    </div>

</div>
"""

m.get_root().html.add_child(
    folium.Element(title_html)
)


# =========================================================
# СОХРАНЯЕМ
# =========================================================

m.save(OUTPUT_FILE)


print()
print("=" * 50)

print(
    f"Карта сохранена: {OUTPUT_FILE}"
)

print(
    f"Всего точек: {len(all_points)}"
)

print(
    f"Количество годов: {len(updated_sheets)}"
)

print("=" * 50)
