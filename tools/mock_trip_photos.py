"""
Mock trip photos generator with EXIF metadata for VW California Travel Memory.

Generates realistic mock road trip photos with accurate GPS coordinates,
chronological timestamps, and camera metadata for presentation and testing.
Curated specifically for the Poznań -> Warszawa route (11.09.2026 - 14.09.2026).
"""

import os
import shutil
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import piexif

from tools.extract_exif import extract_exif


# Curated route waypoints and photo metadata for Poznań -> Warszawa
POZNAN_WARSZAWA_MOCK_PHOTOS = [
    {
        "filename": "01_Poznan_Stary_Rynek.jpg",
        "source_asset": "poznan.jpg",
        "title": "Poznań — Stary Rynek i Ratusz",
        "description": (
            "Poranny start wyprawy VW California ze Starego Rynku w Poznaniu. "
            "Renesansowy ratusz i kolorowe kamieniczki."
        ),
        "lat": 52.4082,
        "lng": 16.9340,
        "date_str": "2026-09-11 10:15:00",
        "day_number": 1,
        "location_label": "Poznań, Stary Rynek",
    },
    {
        "filename": "02_Kornik_Zamek_i_Jezioro.jpg",
        "source_asset": "kornik.jpg",
        "title": "Kórnik — Zamek Neogotycki i Jezioro Kórnickie",
        "description": (
            "Popołudniowy postój przy neogotyckim Zamku w Kórniku "
            "i promenadzie nad Jeziorem Kórnickim."
        ),
        "lat": 52.2447,
        "lng": 17.0911,
        "date_str": "2026-09-11 16:30:00",
        "day_number": 1,
        "location_label": "Kórnik, Zamek",
    },
    {
        "filename": "03_Powidz_Jezioro_Powidzkie.jpg",
        "source_asset": "powidz.jpg",
        "title": "Powidz — Jezioro Powidzkie i Vanlife Camping",
        "description": (
            "Poranek z podniesionym dachem sypialnym campervana nad krystalicznym "
            "Jeziorem Powidzkim w otoczeniu lasu sosnowego."
        ),
        "lat": 52.4172,
        "lng": 17.9189,
        "date_str": "2026-09-12 09:15:00",
        "day_number": 2,
        "location_label": "Powidz / Przybrodzin",
    },
    {
        "filename": "04_Uniejow_Zamek_i_Termy.jpg",
        "source_asset": "uniejow.jpg",
        "title": "Uniejów — Zamek Arcybiskupów i Termy nad Wartą",
        "description": (
            "Złota godzina nad brzegiem Warty z widokiem na XIV-wieczny Zamek "
            "w Uniejowie i relaks w basenach termalnych."
        ),
        "lat": 51.9731,
        "lng": 18.7944,
        "date_str": "2026-09-12 17:45:00",
        "day_number": 2,
        "location_label": "Uniejów, Zamek nad Wartą",
    },
    {
        "filename": "05_Arkadia_Park_Romantyczny.jpg",
        "source_asset": "arkadia.jpg",
        "title": "Arkadia — Romantyczny Park Heleny Radziwiłłowej",
        "description": (
            "Przystanek przy zabytkowym akwedukcie rzymskim i malowniczym "
            "stawie w Arkadii pod Łowiczem."
        ),
        "lat": 52.1242,
        "lng": 20.0175,
        "date_str": "2026-09-13 11:30:00",
        "day_number": 3,
        "location_label": "Arkadia k. Łowicza",
    },
    {
        "filename": "06_Zelazowa_Wola_Dworek_Chopina.jpg",
        "source_asset": "zelazowa_wola.jpg",
        "title": "Żelazowa Wola — Park i Miejsce Urodzenia Chopina",
        "description": (
            "Spacer po zabytkowym parku krajobrazowym i alejach wierzbowych "
            "wokół dworku Fryderyka Chopina."
        ),
        "lat": 52.2575,
        "lng": 20.3150,
        "date_str": "2026-09-13 16:00:00",
        "day_number": 3,
        "location_label": "Żelazowa Wola, Dworek Chopina",
    },
    {
        "filename": "07_Kampinos_Puszcza_i_Kladka.jpg",
        "source_asset": "kampinos.jpg",
        "title": "Kampinoski Park Narodowy — Ścieżka Kładką i Puszcza",
        "description": (
            "Poranna leśna wyprawa ścieżką dydaktyczną z drewnianą kładką "
            "przez torfowiska i bory sosnowe Puszczy Kampinoskiej."
        ),
        "lat": 52.2853,
        "lng": 20.4578,
        "date_str": "2026-09-14 10:30:00",
        "day_number": 4,
        "location_label": "Puszcza Kampinoska, Granica",
    },
    {
        "filename": "08_Warszawa_Bulwary_Wislane.jpg",
        "source_asset": "warszawa.jpg",
        "title": "Warszawa — Bulwary Wiślane i Meta Podróży",
        "description": (
            "Finał 4-dniowej wyprawy na Bulwarach Wiślanych w Warszawie "
            "z widokiem na panoramę Zamku Królewskiego i rzekę Wisłę."
        ),
        "lat": 52.2472,
        "lng": 21.0135,
        "date_str": "2026-09-14 16:45:00",
        "day_number": 4,
        "location_label": "Warszawa, Bulwary Wiślane",
    },
]


def _coord_to_deg(value, loc_refs):
    """
    Convert decimal coordinates to EXIF rational tuple ((deg, 1), (min, 1), (sec, 10000)).

    Args:
        value (float): Decimal degrees.
        loc_refs (list): Two-element list of hemisphere refs, e.g. ['S', 'N'] or ['W', 'E'].

    Returns:
        tuple: (rational_tuple, ref_char)
    """
    if value < 0:
        loc_ref = loc_refs[0]
    elif value > 0:
        loc_ref = loc_refs[1]
    else:
        loc_ref = loc_refs[1]

    abs_val = abs(value)
    deg = int(abs_val)
    rem = (abs_val - deg) * 60
    min_val = int(rem)
    sec_val = (rem - min_val) * 60
    sec_num = int(round(sec_val * 10000))

    if sec_num >= 600000:
        sec_num -= 600000
        min_val += 1
    if min_val >= 60:
        min_val -= 60
        deg += 1

    return ((deg, 1), (min_val, 1), (sec_num, 10000)), loc_ref


def _create_fallback_image(info, output_path):
    """
    Generate a styled canvas image if master asset is not available.

    Args:
        info (dict): Photo metadata dict.
        output_path (str): Target file path.
    """
    width, height = 1600, 1200
    img = Image.new("RGB", (width, height), color=(0, 30, 80))
    draw = ImageDraw.Draw(img)

    # Gradient header block
    draw.rectangle([(0, 0), (width, 140)], fill=(0, 14, 38))
    draw.rectangle([(0, height - 120), (width, height)], fill=(0, 14, 38))

    try:
        font_large = ImageFont.truetype("arial.ttf", 52)
        font_sub = ImageFont.truetype("arial.ttf", 34)
    except IOError:
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    draw.text((60, 45), "VOLKSWAGEN CALIFORNIA TRAVEL MEMORY", fill=(0, 180, 255), font=font_large)
    draw.text((60, 220), info["title"], fill=(255, 255, 255), font=font_large)
    draw.text((60, 310), f"Data: {info['date_str']} | Dzień {info['day_number']}", fill=(200, 220, 255), font=font_sub)
    draw.text((60, 370), f"GPS: {info['lat']:.4f}° N, {info['lng']:.4f}° E ({info['location_label']})", fill=(180, 200, 230), font=font_sub)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, "JPEG", quality=92)


def create_mock_photo_with_exif(source_img_path, output_path, info):
    """
    Create a photo file with complete EXIF GPS and timestamp metadata injected.

    Args:
        source_img_path (str): Path to master visual image (or None for fallback).
        output_path (str): Destination path for final JPG.
        info (dict): Metadata containing lat, lng, date_str, title, description.

    Returns:
        bool: True on success.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    if source_img_path and os.path.exists(source_img_path):
        img = Image.open(source_img_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
    else:
        _create_fallback_image(info, output_path)
        img = Image.open(output_path)

    # Build EXIF structure
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    # Timestamp
    dt = datetime.strptime(info["date_str"], "%Y-%m-%d %H:%M:%S")
    exif_time = dt.strftime("%Y:%m:%d %H:%M:%S").encode("utf-8")
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = exif_time
    exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = exif_time
    exif_dict["0th"][piexif.ImageIFD.DateTime] = exif_time

    # Device & Brand metadata
    exif_dict["0th"][piexif.ImageIFD.Make] = "Volkswagen"
    exif_dict["0th"][piexif.ImageIFD.Model] = "California T6.1 Ocean DashCam"
    exif_dict["0th"][piexif.ImageIFD.Software] = "VW California Travel Memory Engine v2.0"
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = info["title"].encode("utf-8")

    # GPS coordinates
    lat_deg, lat_ref = _coord_to_deg(info["lat"], ["S", "N"])
    lng_deg, lng_ref = _coord_to_deg(info["lng"], ["W", "E"])

    exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat_ref
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = lat_deg
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lng_ref
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = lng_deg
    exif_dict["GPS"][piexif.GPSIFD.GPSDateStamp] = dt.strftime("%Y:%m:%d").encode("utf-8")

    exif_bytes = piexif.dump(exif_dict)
    img.save(output_path, "JPEG", exif=exif_bytes, quality=94)
    return True


def generate_poznan_warszawa_mock_photos(
    primary_dir=None,
    also_copy_to_root=True,
    verbose=True,
):
    """
    Generate all 8 mock photos for the Poznań -> Warszawa route.

    Args:
        primary_dir (str, optional): Target directory. Defaults to 'test-materials-exif/poznan_warszawa'.
        also_copy_to_root (bool): If True, also copies photos to 'mock_photos_poznan_warszawa/'
                                  for quick drag-and-drop presentation access.
        verbose (bool): Print status report.

    Returns:
        list: List of dicts containing generated photo results and verified EXIF data.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if primary_dir is None:
        primary_dir = os.path.join(project_root, "test-materials-exif", "poznan_warszawa")

    root_mock_dir = os.path.join(project_root, "mock_photos_poznan_warszawa")
    source_assets_dir = os.path.join(project_root, "tools", "assets", "mock_photos_source")

    os.makedirs(primary_dir, exist_ok=True)
    if also_copy_to_root:
        os.makedirs(root_mock_dir, exist_ok=True)

    results = []

    if verbose:
        print("\n================================================================================")
        print("📸 GENEROWANIE ZDJĘĆ MOCKOWYCH DLA TRASY POZNAŃ -> WARSZAWA (11.09 - 14.09.2026)")
        print("================================================================================")
        print(f"Katalog docelowy: {primary_dir}")
        if also_copy_to_root:
            print(f"Katalog prezentacyjny (root): {root_mock_dir}")
        print("--------------------------------------------------------------------------------")

    for item in POZNAN_WARSZAWA_MOCK_PHOTOS:
        src_path = os.path.join(source_assets_dir, item["source_asset"])
        out_path = os.path.join(primary_dir, item["filename"])

        create_mock_photo_with_exif(src_path, out_path, item)

        if also_copy_to_root:
            root_out_path = os.path.join(root_mock_dir, item["filename"])
            shutil.copy2(out_path, root_out_path)

        # Verify through extract_exif
        verification = extract_exif(out_path)
        meta = verification.get("metadata", {})

        file_size_kb = round(os.path.getsize(out_path) / 1024, 1)

        record = {
            "filename": item["filename"],
            "title": item["title"],
            "day_number": item["day_number"],
            "date": item["date_str"],
            "captured_at": meta.get("captured_at"),
            "lat": meta.get("lat"),
            "lng": meta.get("lng"),
            "camera_make": meta.get("camera_make"),
            "camera_model": meta.get("camera_model"),
            "size_kb": file_size_kb,
            "filepath": out_path,
            "exif_status": verification.get("status"),
        }
        results.append(record)

        if verbose:
            print(
                f"[{record['day_number']}/4] {record['filename']:<33} | "
                f"{record['date']:<19} | "
                f"({record['lat']:.4f}, {record['lng']:.4f}) | "
                f"{record['size_kb']} KB | EXIF: {record['exif_status'].upper()}"
            )

    if verbose:
        print("================================================================================")
        print(f"✅ Pomyślnie wygenerowano i zweryfikowano {len(results)} zdjęć mockowych!")
        print("================================================================================\n")

    return results


def get_poznan_warszawa_photos_metadata():
    """Return the raw metadata definition list for Poznań -> Warszawa photos."""
    return POZNAN_WARSZAWA_MOCK_PHOTOS


if __name__ == "__main__":
    generate_poznan_warszawa_mock_photos()
