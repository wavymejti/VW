import os
import argparse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import piexif

def _to_deg(value, loc):
    """Convert decimal coordinates to degrees, minutes and seconds tuple for EXIF."""
    if value < 0:
        loc_value = loc[0]
    elif value > 0:
        loc_value = loc[1]
    else:
        loc_value = ""
    abs_value = abs(value)
    deg = int(abs_value)
    t1 = (abs_value - deg) * 60
    min_val = int(t1)
    sec_val = round((t1 - min_val) * 60 * 10000)
    
    return ((deg, 1), (min_val, 1), (sec_val, 10000)), loc_value

def generate_mock_photo(output_path, lat, lng, date_str, color=(0, 30, 80)):
    """
    Generate a simple color block image with EXIF GPS and timestamp data.
    """
    # Create a solid color image
    img = Image.new('RGB', (800, 600), color=color)
    d = ImageDraw.Draw(img)
    
    # Add some text to the image so it's not totally blank
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except IOError:
        font = ImageFont.load_default()
        
    text = f"Lat: {lat}\nLng: {lng}\nDate: {date_str}"
    d.text((50, 50), text, fill=(255, 255, 255), font=font)
    
    # Setup EXIF data
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    
    # Set DateTimeOriginal
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        exif_time = dt.strftime("%Y:%m:%d %H:%M:%S").encode("utf-8")
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = exif_time
    except Exception as e:
        print(f"Warning: Could not parse date '{date_str}': {e}")
    
    # Set GPS coordinates
    lat_deg, lat_ref = _to_deg(lat, ["S", "N"])
    lng_deg, lng_ref = _to_deg(lng, ["W", "E"])
    
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat_ref
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = lat_deg
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lng_ref
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = lng_deg
    
    exif_bytes = piexif.dump(exif_dict)
    
    # Save image with EXIF
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, "jpeg", exif=exif_bytes)
    print(f"Successfully created mock photo at: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a mock photo with EXIF data.")
    parser.add_argument("output", help="Output file path (e.g., photo.jpg)")
    parser.add_argument("--lat", type=float, required=True, help="Latitude")
    parser.add_argument("--lng", type=float, required=True, help="Longitude")
    parser.add_argument("--date", type=str, required=True, help="Date in 'YYYY-MM-DD HH:MM:SS' format")
    
    args = parser.parse_args()
    generate_mock_photo(args.output, args.lat, args.lng, args.date)
