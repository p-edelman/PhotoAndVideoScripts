#!/usr/bin/env python3

import datetime, sys, subprocess, os.path, re, time

RE_TIME = re.compile("([0-9]{1,2}):([0-9]{1,2}):([0-9]{1,2})")

if __name__ == "__main__":
  photo_file    = None
  time_on_photo = None
  
  if len(sys.argv) == 3:
    if os.path.exists(sys.argv[1]) and os.path.isfile(sys.argv[1]):
      photo_file = sys.argv[1]
    
    match = RE_TIME.match(sys.argv[2])
    if match:
      time_on_photo = time.mktime((0, 0, 0, int(match.group(1)), int(match.group(2)), int(match.group(3)), 0, 0, -1))
  
  # Parse time the user has give
  if not (photo_file and time_on_photo):
    print("Tell the time adjustment that needs to be made on this photo")
    print("Usage: %s IMAGE_FILE HH:MM:SS" % sys.argv[0])
    sys.exit(1)

  # Figure out the EXIF datetime
  result = subprocess.run(["exiftool", "-CreateDate", "-S", "-dateFormat", "%H:%M:%S", photo_file], stdout = subprocess.PIPE)
  if result.returncode != 0:
    print("Couldn't run exiftool. Aborting")
    sys.exit(1)
  match = RE_TIME.search(str(result.stdout))
  time_exif = time.mktime((0, 0, 0, int(match.group(1)), int(match.group(2)), int(match.group(3)), 0, 0, -1))
  
  # Output the difference
  diff  = int(time_on_photo - time_exif)
  if diff != 0:
    sign = diff / abs(diff)   # Determine if we should add or subtract
    diff = abs(diff)          # Make the number of seconds positive
    hours = diff / (60 * 60)  # Calculate the hours
    diff = diff % (60 * 60)   # Determine remaining seconds
    minutes = diff / 60       # Convert remaining seconds to minutes
    seconds = diff % 60       # And save the remainder
    print("To correct the time for this photo, adjust it by %s%02d:%02d:%02d" % ("+" if sign == 1 else "-", hours, minutes, seconds))
  else:
    print("Time is already correct")
  