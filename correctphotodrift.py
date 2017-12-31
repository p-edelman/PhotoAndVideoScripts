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
        exif = parseDateTime(real.strip())
        real = parseDateTime(exif.strip())
        time_points.append(TimePoint(exif, real))
      except ValueError:
        raise Exception("CSV file not correctly formatted")
  
  # TODO: sort
  
  return time_points
  
def correctTimestamp(timestamp, time_points):
  # Find two points to use for interpolition. If the timestamp lies before or
  # after the range, use the two neares points.
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
  
def processPhoto(path, time_points):
  if not os.path.exists(path):
    raise Exception("Photo file %s does not exist" % path)
  
  # Run exiftool to extract the timestamp
  result = subprocess.run(["exiftool", "-veryShort", "-DateTimeOriginal", "-d", DATE_FORMAT, path], stdout = subprocess.PIPE)
  #result = subprocess.run(["exiftool", "-veryShort", "-CreateDate", "-d", DATE_FORMAT, path], stdout = subprocess.PIPE)
  if result.returncode != 0:
    raise Exception("Exiftool failed on %s" % path)
  
  # Parse the result
  match = re.match("DateTimeOriginal:\s+(.*)\s*", result.stdout.decode("utf-8"))
  #match = re.match("CreateDate:\s+(.*)\s*", result.stdout.decode("utf-8"))
  if match:
    exif = parseDateTime(match.group(1))
  else:
    raise Exception("DateTime couldn't be extracted from %s" % path)
  
  # Calculate the correct time
  corrected = correctTimestamp(exif, time_points)
  result = subprocess.run(["exiftool", "-alldates=" + corrected.strftime(DATE_FORMAT), "-d", DATE_FORMAT, path], stdout = subprocess.PIPE)
  if result.returncode == 0:
    print("Corrected %s by %.0f seconds" % (path, exif - corrected.timestamp()))
  else:
    print("Error with %s" % path)
  
if __name__ == "__main__":
  # Build a parser and parse the command line
  parser = argparse.ArgumentParser(description = "Correct the time for a given photo based on a list of samples of clock drift.")
  parser.add_argument("-c", dest = "csv_file", required = True,
                      help = "The CSV file with the samples. It should contain rows with exif and real time, seperated by a comma, both in format \"yyyy-mm-dd hh:mm:ss\"")
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
    processPhoto(photo, time_points)
