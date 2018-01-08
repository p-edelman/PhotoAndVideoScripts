#!/usr/bin/env python3

import argparse, datetime, os.path, re, subprocess

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

class TimePoint:
  def __init__(self, exif, real):
    self.exif = exif
    self.real = real

def parseDateTime(datetime_string):
  dt = datetime.datetime.strptime(datetime_string, DATE_FORMAT)
  return dt.timestamp()
  
def readCSVFile(path):
  if not os.path.exists(path):
    raise Exception("CSV file doesn't exist")

  time_points = []
  
  with open(path, "r") as in_file:
    for line in in_file.readlines():
      try:
        exif, real = line.split(",")
        exif = parseDateTime(exif.strip())
        real = parseDateTime(real.strip())
        time_points.append(TimePoint(exif, real))
      except ValueError:
        raise Exception("CSV file not correctly formatted")
  
  # TODO: sort
  
  return time_points
  
def correctTimestamp(timestamp, time_points):
  # Find two points to use for interpolation. If the timestamp lies before or
  # after the range, use the two nearest points.
  if timestamp <= time_points[0].exif:
    start = time_points[0]
    end   = time_points[1]
  elif timestamp >= time_points[-1].exif:
    start = time_points[-2]
    end   = time_points[-1]
  else:
    for i in range(len(time_points) - 1):
      if timestamp >= time_points[i].exif and timestamp < time_points[i + 1].exif:
        start = time_points[i]
        end   = time_points[i + 1]
        break
  
  # Find the slope and offset to map an exif time on real time
  slope  = (end.real - start.real) / (end.exif - start.exif)
  offset = start.real - start.exif * slope
  
  # Use these values to calculate the correct time
  return datetime.datetime.fromtimestamp(round(timestamp * slope + offset))

def processPhoto(photo_path, time_points, dry_run = False):
  """ Correct the time stamp of the photo specified at photo_path, using the
      time_points tuple to interpolate to the correct time. The result will be
      printed to stdout.
      If dry_run is True, nothing will be actually written. """
      
  if not os.path.exists(photo_path):
    raise Exception("Photo file %s does not exist" % photo_path)
  
  # Run exiftool to extract the timestamp. We try both the DateTimeOriginal and
  # CreateDate tags, because one of them might be absent
  exif = None
  for tag in ["DateTimeOriginal", "CreateDate"]:
    result = subprocess.run(["exiftool", "-veryShort", "-%s" % tag, "-d", DATE_FORMAT, photo_path], stdout = subprocess.PIPE)
    if result.returncode != 0:
      raise Exception("Exiftool failed on %s" % photo_path)
  
    # Parse the result
    match = re.match("%s:\s+(.*)\s*" % tag, result.stdout.decode("utf-8"))
    if match:
      exif = parseDateTime(match.group(1))
      break
  
  if not exif:
    raise Exception("DateTime couldn't be extracted from %s" % photo_path)
  
  # Calculate the correct time
  corrected = correctTimestamp(exif, time_points)
  
  # Write the corrected time to the photo file
  if not dry_run:
    result = subprocess.run(["exiftool", "-alldates=" + corrected.strftime(DATE_FORMAT), "-d", DATE_FORMAT, photo_path], stdout = subprocess.PIPE)
    if result.returncode == 0:
      print("Shifted %s by %+.0f seconds" % (photo_path, corrected.timestamp() - exif))
    else:
      print("Error with %s" % photo_path)
  else:
    print("%s will be shifted by %+.0f seconds" % (photo_path, corrected.timestamp() - exif))
  
if __name__ == "__main__":
  # Build a parser and parse the command line
  parser = argparse.ArgumentParser(description = "Correct the time for a given photo based on a list of samples of clock drift.")
  parser.add_argument("-n", "--dry-run", action = "store_true",
                      help = "Don't alter any files, just print out what would be done")
  parser.add_argument('csv_file', type = str, help = "The CSV file with the samples. It should contain rows with exif and real time, seperated by a comma, both in format \"yyyy-mm-dd hh:mm:ss\"")
  parser.add_argument('photo', type = str, nargs = "+")
  
  args = parser.parse_args()
 
  # Check if exiftool is there
  try:
    status = subprocess.run(["exiftool", "-ver"], stdout = subprocess.PIPE)
  except FileNotFoundError:
    raise Exception("Please install Exiftool")
  if status.returncode != 0:
    raise Exception("Exiftool can't be run")
  
  time_points = readCSVFile(args.csv_file)

  for photo in args.photo:
    processPhoto(photo, time_points, args.dry_run)
