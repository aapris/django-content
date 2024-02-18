"""
Read exif tags from a file using exifread module.

Currently, following values are returned in usable format,
if they were available:

- lat (float)
- lon (float)
- direction (float)
- direction_ref ('T' or 'M')
- altitude (float)
- gpstime (timezone aware datetime, tzinfo=<UTC>)
"""

import datetime
import logging
from fractions import Fraction
from typing import Optional
from zoneinfo import ZoneInfo

import exifread
import timezonefinder

log = logging.getLogger("exifparser")


def read_exif(filepath: str, details: bool = False) -> dict:
    """
    Use exifread module to read EXIF tags from a file.
    """
    with open(filepath, "rb") as f:
        try:
            exif = exifread.process_file(f, details=details)
        except IndexError:
            exif = None
    return exif


def _get_if_exist(data: dict, key: str) -> Optional[str]:
    """
    Get item by a key from exifread's weird tag format
    """
    if key in data:
        return data[key]
    # ExifRead 2.0 added weird 'EXIF ' prefix to GPS tags
    key = "EXIF " + key
    if key in data:
        return data[key]
    return None


def _convert_to_float(val: str) -> float:
    """
    Use Fraction() to convert a string value like '1212/25' to a float.
    """
    try:
        f = float(Fraction(str(val)))
    except ZeroDivisionError:
        f = 0
        log.warning("_convert_to_float({}) failed".format(val))
    return f


def _convert_to_degrees(value: list) -> float:
    """
    Convert the GPS coordinates stored in the EXIF to degrees in float format,
    e.g. [24, 57, 1212/25] -> 24.963466666666665
    """
    d = _convert_to_float(value.values[0])
    m = _convert_to_float(value.values[1])
    s = _convert_to_float(value.values[2])
    f = d + (m / 60.0) + (s / 3600.0)
    return f


def parse_gps_latlon(exif: dict) -> dict:
    """
    Return the latitude and longitude, if available,
    from the provided exif data (obtained through read_exif() above)
    """
    data = {}
    if "Image GPSInfo" in exif:
        gps_latitude = _get_if_exist(exif, "GPS GPSLatitude")
        if _get_if_exist(exif, "GPS GPSLatitudeRef") is None:
            return data  # missing coordinates
        gps_latitude_ref = _get_if_exist(exif, "GPS GPSLatitudeRef").values
        gps_longitude = _get_if_exist(exif, "GPS GPSLongitude")
        gps_longitude_ref = _get_if_exist(exif, "GPS GPSLongitudeRef").values

        if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
            lat = _convert_to_degrees(gps_latitude)
            if gps_latitude_ref != "N":
                lat = -lat
            lon = _convert_to_degrees(gps_longitude)
            if gps_longitude_ref != "E":
                lon = -lon
            data = {"lat": lat, "lon": lon}
    return data


def parse_gps_float(exif: dict, tagname: str) -> Optional[float]:
    """
    Return the float parsed from 'tagname', if available,
    from the provided exif data (obtained through read_exif() above)
    """
    #    d = _convert_to_float(value.values[0])
    val = None
    if "Image GPSInfo" in exif:
        tag = _get_if_exist(exif, tagname)
        if tag is None:
            return None  # missing tag
        val = _convert_to_float(tag.values[0])
    return val


def parse_gps_altitude(exif: dict) -> dict:
    """
    Return the altitude, if available,
    from the provided exif data (obtained through read_exif() above)
    """
    data = {}
    val = parse_gps_float(exif, "GPS GPSAltitude")
    if val is None:
        return data  # missing altitude
    gps_altitude_ref = _get_if_exist(exif, "GPS GPSAltitudeRef")
    # In some rare situations gps_altitude_ref may be missing
    if gps_altitude_ref and gps_altitude_ref.values[0] == "1":
        val = -val
    data = {"altitude": val}
    return data


def parse_gps_direction(exif: dict) -> dict:
    """
    Return the direction, if available,
    from the provided exif data (obtained through read_exif() above)
    'T' = True direction
    'M' = Magnetic direction
    """
    data = {}
    val = parse_gps_float(exif, "GPS GPSImgDirection")
    if val is None:
        return data  # missing direction
    data = {"direction": val}
    gps_direction_ref = _get_if_exist(exif, "GPS GPSImgDirectionRef").values
    if gps_direction_ref:
        data["direction_ref"] = gps_direction_ref[0]
        # Currently do nothing with direction reference
        if gps_direction_ref[0] == "T":
            pass
        elif gps_direction_ref[0] == "M":
            pass
    return data


def parse_gpstime(exif: dict) -> dict:
    """
    Parse GPS timestamp if found in EXIF tags.
    Return timezone aware datetime object.
    """
    data = {}
    gps_timestamp = _get_if_exist(exif, "GPS GPSTimeStamp")
    gps_date = _get_if_exist(exif, "GPS GPSDate")
    if gps_date and gps_timestamp:
        yy, mm, dd = [int(x) for x in str(gps_date).split(":")]
        hh, _min, ss = [x.num for x in gps_timestamp.values]
        try:
            dt = datetime.datetime(yy, mm, dd, hh, _min, ss)
            aware_dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            data["gpstime"] = aware_dt
        except ValueError as err:
            log.warning(f"Failed to parse_gpstime: {err}")
            # Sometimes GPS timestamps really are broken.
            # print(gps_date)
            # print(gps_timestamp, gps_timestamp.values[0])
            # print(type(gps_timestamp.values[0]))
            # print("FOO", float(Fraction(str(gps_timestamp.values[0]))))
            # print(yy, mm, dd, hh, _min, ss)
            # print(exif)
            # aware_dt = None
            # raise
            pass
    return data


def parse_datetime(exif: dict, tag_name="EXIF DateTimeOriginal", gps=None) -> dict:
    """
    Parse datetime from exif tag tagname, which is DateTime type and a string
    like "2014:05:22 14:37:51".
    Return timezone aware datetime in a dict, if latitude and longitude were found in gps, e.g.
    {'creation_time': datetime.datetime(2022, 3, 30, 11, 14, 39, tzinfo=<DstTzInfo 'Europe/Helsinki' EEST+3:00:00 DST>)}
    """
    data = {}
    if tag_name in exif:
        orig_val = val = str(exif[tag_name])
        val = val.strip("\0")  # remove possible null bytes
        try:
            data["creation_time"] = datetime.datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
            # Determine timezone from latitude and longitude, if they are present
            if gps is not None and "lat" in gps and "lon" in gps:
                tf = timezonefinder.TimezoneFinder()
                tz = tf.timezone_at(lng=gps["lon"], lat=gps["lat"])
                data["creation_time"] = data["creation_time"].replace(tzinfo=ZoneInfo(tz))
        except ValueError as err:  # E.g. value is '0000:00:00 00:00:00\x00'
            log.warning("parse_datetime({}) failed: {}".format(orig_val, err))
        except TypeError as err:  # E.g. value is '4:24:26\x002004:06:25 0'
            log.warning("parse_datetime({}) failed: {}".format(orig_val, err))
        except Exception as err:
            log.warning("parse_datetime({}) failed: {}".format(orig_val, err))
    return data


def parse_gps(exif: dict) -> dict:
    """
    Parse all supported GPS related tags from exif tags and return
    values usable in python.
    """
    gps = parse_gps_latlon(exif)
    gpstime = parse_gpstime(exif)
    gps.update(gpstime)
    gps_altitude = parse_gps_altitude(exif)
    gps.update(gps_altitude)
    gps_direction = parse_gps_direction(exif)
    gps.update(gps_direction)
    return gps


def main():
    import sys

    for filepath in sys.argv[1:]:
        exif = read_exif(filepath)
        gps = parse_gps(exif)
        print(filepath, exif)
        print(parse_datetime(exif, tag_name="EXIF DateTimeOriginal", gps=gps))


if __name__ == "__main__":
    main()
