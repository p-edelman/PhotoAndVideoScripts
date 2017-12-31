# A collection of useful scripts to manipulate photo and video files

## telltimeadjustment.py

A script that let's you figure out the offset of the camera clock. It works by taking a picture of a second-accurate clock and comparing that to the EXIF time.

### Requirements

- Python3
- Exiftool

### Usages

First, take a picture of a second-accurate clock (a GPS, a computer synced by NTP, etc.) with the camera you want to know about. Download the picture and write down the time you see on it in the format HH:MM:SS

Then, run:

    telltimeadjustment.py IMAGE_FILE TIMESTAMP

The result will be the offset off the camera to the actual time.
