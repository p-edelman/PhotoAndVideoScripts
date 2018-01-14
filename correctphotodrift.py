#!/usr/bin/env python3

import argparse, datetime, os.path, re, subprocess, sys

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

class TimePoint:
  def __init__(self, exif, real):
    self.exif = exif
    self.real = real

class MetaDataDateTime:
  known_tags = [
    "DateTimeOriginal",
    "CreateDate",
    "MediaCreateDate",
    "MediaModifyDate",
    "TrackCreateDate",
    "TrackModifyDate"]

  def __init__(self, path, ignore_read_tags = []):
    self._path = path
    
    # The list of datetime related tags that we have in the metadata
    self._tags = []
    
    # The datetime of the image as a seconds since epoch float
    self._original_dt  = None
    self._corrected_dt = None
    
    # Read the metadata
    self.dt_tag = self._readMetaData(ignore_read_tags)

  def _readMetaData(self, ignore_read_tags):
    """ Read the relevant metadata from the image file. This sets the 
        self._datatime and self._tags parameters.
        It returns the name of the tag that was used for deterimining the
        datetime. """

    # Construct the command arguments
    cmd = ["exiftool", "-veryShort", "-d", DATE_FORMAT]
    for tag in self.known_tags: # Add every possible date tag
      cmd.append("-%s" % tag)
    cmd.append(self._path)

    # Run exiftool
    result = subprocess.run(cmd, stdout = subprocess.PIPE)
    if result.returncode != 0:
      raise Exception("Exiftool failed on %s" % self._path)
    stdout = result.stdout.decode("utf-8")
    
    # Analyze the result
    used_tag = None
    for tag in self.known_tags:
      if tag in stdout:
        self._tags.append(tag)
        
        # Extract the datetime if we don't have it yet
        if not self._original_dt and tag not in ignore_read_tags:
          match = re.search("%s:\s+(.*)\s*" % tag, stdout)
          if match:
            used_tag = tag
            self._original_dt = parseDateTime(match.group(1))
    
    if not self._original_dt:
      raise Exception("Couldn't read date and time information from %s" % self._path)

    return used_tag
    
  def calcCorrection(self, reference_points):
    """ Calculate the corrected the datetime based on the list of reference
        points. """
    
    # Find two points to use for interpolation. If the timestamp lies before or
    # after the range, use the two nearest points.
    if self._original_dt <= reference_points[0].exif:
      start = reference_points[0]
      end   = reference_points[1]
    elif self._original_dt >= reference_points[-1].exif:
      start = reference_points[-2]
      end   = reference_points[-1]
    else:
      for i in range(len(reference_points) - 1):
        if self._original_dt >= reference_points[i].exif and \
           self._original_dt < reference_points[i + 1].exif:
          start = reference_points[i]
          end   = reference_points[i + 1]
          break
    
    # Find the slope and offset to map an exif time on real time
    slope  = (end.real - start.real) / (end.exif - start.exif)
    offset = start.real - start.exif * slope
    
    # Use these values to calculate the correct time
    self._corrected_dt = round(self._original_dt * slope + offset)
    
    return self._corrected_dt - self._original_dt
    
  def writeMetaData(self):
    """ Write the corrected datetime to the metadata. Return True on success,
        False on failure.
        NOTE: you need to run calcCorrection() first. """
        
    if not self._corrected_dt:
      raise Exception("You need to run the calcCorrection() method first!")

    # Construct the Exiftool command by setting all known tags to the new stamp
    cmd = ["exiftool", "-d", DATE_FORMAT]
    dt_str = datetime.datetime.fromtimestamp(self._corrected_dt).strftime(DATE_FORMAT)
    for tag in self._tags:
      cmd.append("-%s=%s" % (tag, dt_str))
    cmd.append(self._path)

    # Run Exiftool
    result = subprocess.run(cmd, stdout = subprocess.PIPE)
    if result.returncode == 0:
      return True
    
    return False
    
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
  
def processPhoto(photo_path, reference_points, ignore_read_tags = [], dry_run = False):
  """ Correct the datetime stamp of the photo specified at photo_path, using the
      reference_points list of tuples to interpolate to the correct time.
      The results will be printed to stdout / stderr.
      The ignore_read_tags is a list of tags that shouldn't be used for
      determining the datetime stamp of the photo.
      If dry_run is True, the photo isn't actually modified. """
      
  if not os.path.exists(photo_path):
    raise Exception("Photo file %s does not exist" % photo_path)
  
  try:
    metadata = MetaDataDateTime(photo_path, ignore_read_tags)
  except:
    sys.stdout.write("The date and time couldn't be extracted from %s" % photo_path)
    sys.exit(1)
  
  # Calculate the correct time
  diff = metadata.calcCorrection(reference_points)
  
  # Write the corrected time to the photo file
  if not dry_run:
    if metadata.writeMetaData():
      print("Shifted %s (from %s tag) by %+.0f seconds" % (photo_path, metadata.dt_tag, diff))
    else:
      print("Error with %s" % photo_path)
  else:
    print("%s will be shifted (from %s tag) by %+.0f seconds" % (photo_path, metadata.dt_tag, diff))
  
if __name__ == "__main__":
  # Build a parser and parse the command line
  parser = argparse.ArgumentParser(description = "Correct the time for a given photo based on a list of samples of clock drift.")
  parser.add_argument("-n", "--dry-run", action = "store_true",
                      help = "Don't alter any files, just print out what would be done")
  tag_group = parser.add_mutually_exclusive_group()
  tag_group.add_argument("-i", "--ignore-reading",
                         choices = MetaDataDateTime.known_tags,
                         action = "append",
                         help = "Ignore this tag for reading the datetime (it will be included when writing though). This tag can be used multiple times.")
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
  
  reference_points = readCSVFile(args.csv_file)

  ignore_read_tags = args.ignore_reading if args.ignore_reading else []
  for photo in args.photo:
    processPhoto(photo, reference_points, ignore_read_tags, args.dry_run)
