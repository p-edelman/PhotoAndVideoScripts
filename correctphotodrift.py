#!/usr/bin/env python3

import argparse, datetime, os.path, re, subprocess, sys

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"
DT_FORMAT   = "%s %s" % (DATE_FORMAT, TIME_FORMAT)

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

    # The DateTime of the image and the tag where it came from
    self.dt, self.dt_tag = self._readMetaData(ignore_read_tags)

    # The corrected datetime of the image. This can be determined using the
    # calcCorrection() method
    self._corrected_dt = None

  def _readMetaData(self, ignore_read_tags):
    """ Read the relevant metadata from the image file. It returns the DateTime
        object of the image and the name of the tag that was used for
        deterimining it. """

    # Construct the command arguments
    cmd = ["exiftool", "-veryShort", "-d", DT_FORMAT]
    for tag in self.known_tags: # Add every possible date tag
      cmd.append("-%s" % tag)
    cmd.append(self._path)

    # Run exiftool
    result = subprocess.run(cmd, stdout = subprocess.PIPE)
    if result.returncode != 0:
      raise Exception("Exiftool failed on %s" % self._path)
    stdout = result.stdout.decode("utf-8")
    
    # Analyze the result
    dt       = None
    used_tag = None
    for tag in self.known_tags:
      match = re.search("^%s:\s+(.*)\s*" % tag, stdout, re.MULTILINE)
      if match:
        self._tags.append(tag)
        
        # Extract the datetime if we don't have it yet
        if not dt and tag not in ignore_read_tags:
          used_tag = tag
          dt = datetime.datetime.strptime(match.group(1), DT_FORMAT)
    
    if not dt:
      raise Exception("Couldn't read date and time information from %s" % self._path)

    return dt, used_tag
    
  def calcCorrection(self, reference_points):
    """ Calculate the corrected datetime based on the list of reference points.
        This method sets the self._corrected_dt field and return the offset in
        seconds. """

    original_dt_stamp = self.dt.timestamp()
    
    # Find two points to use for interpolation. If the timestamp lies before or
    # after the range, use the two nearest points.
    if original_dt_stamp <= reference_points[0].exif:
      start = reference_points[0]
      end   = reference_points[1]
    elif original_dt_stamp >= reference_points[-1].exif:
      start = reference_points[-2]
      end   = reference_points[-1]
    else:
      for i in range(len(reference_points) - 1):
        if original_dt_stamp >= reference_points[i].exif and \
           original_dt_stamp < reference_points[i + 1].exif:
          start = reference_points[i]
          end   = reference_points[i + 1]
          break
    
    # Find the slope and offset to map an exif time on real time
    slope  = (end.real - start.real) / (end.exif - start.exif)
    offset = start.real - start.exif * slope
    
    # Use these values to calculate the correct time
    corrected_dt_stamp = round(original_dt_stamp * slope + offset)
    
    self._corrected_dt = datetime.datetime.fromtimestamp(corrected_dt_stamp)    
    return corrected_dt_stamp - original_dt_stamp
    
  def writeMetaData(self):
    """ Write the corrected datetime to the metadata. Return True on success,
        False on failure.
        NOTE: you need to run calcCorrection() first. """
        
    if not self._corrected_dt:
      raise Exception("You need to run the calcCorrection() method first!")

    # Construct the Exiftool command by setting all known tags to the new stamp
    cmd = ["exiftool", "-d", DT_FORMAT]
    dt_str = self._corrected_dt.strftime(DT_FORMAT)
    for tag in self._tags:
      cmd.append("-%s=%s" % (tag, dt_str))
    cmd.append(self._path)

    # Run Exiftool
    result = subprocess.run(cmd, stdout = subprocess.PIPE)
    if result.returncode == 0:
      return True
    
    return False
  
def readCSVFile(path):
  if not os.path.exists(path):
    raise Exception("CSV file doesn't exist")

  time_points = []
  
  with open(path, "r") as in_file:
    for line in in_file.readlines():
      try:
        exif, real = line.split(",")
        exif = datetime.datetime.strptime(exif.strip(), DT_FORMAT).timestamp()
        real = datetime.datetime.strptime(real.strip(), DT_FORMAT).timestamp()
        time_points.append(TimePoint(exif, real))
      except ValueError:
        raise Exception("CSV file not correctly formatted")
  
  time_points.sort(key = lambda point: point.exif)  
  return time_points

def writeCSVFile(path, dt_stamp_pairs):
  with open(path, "w") as out_file:
    dt_stamp_pairs.sort(key = lambda point: point[0])  
    for pair in dt_stamp_pairs:
      if pair:
        out_file.write("%s,%s\n" % (pair[0].strftime(DT_FORMAT), pair[1].strftime(DT_FORMAT)))

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
    sys.stderr.write("The date and time couldn't be extracted from %s\n" % photo_path)
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

def getPhotoAndUserStringDT(photo_path, ignore_tags):
  if not os.path.exists(photo_path):
    sys.stdout.write("Photo file %s does not exist" % photo_path)
    return None
    
  try:
    photo_dt = MetaDataDateTime(photo_path, ignore_read_tags).dt
  except:
    sys.stdout.write("The date and time couldn't be extracted from %s" % photo_path)
    return None
  
  user_dt = None
  photo_date = photo_dt.date()
  while not user_dt:
    user_dt_string = input("%s (date defaults to %s): " % (photo_path, photo_date.strftime(DATE_FORMAT)))
    try:
      user_dt = datetime.datetime.strptime(user_dt_string, DT_FORMAT)
    except ValueError:
      try:
        user_time = datetime.datetime.strptime(user_dt_string, TIME_FORMAT)
        user_dt   = datetime.datetime(photo_date.year, photo_date.month, photo_date.day, user_time.hour, user_time.minute, user_time.second)
      except ValueError:
        print("Invalid datetime string. Format should be %s or %s" % (DT_FORMAT, TIME_FORMAT))
        user_dt = None
  
  return (photo_dt, user_dt)

if __name__ == "__main__":
  # Build a parser and parse the command line
  parser = argparse.ArgumentParser(description = "Correct the time for a given photo based on a list of samples of clock drift.")
  parser.add_argument("-m", "--mode", choices = ["g", "generate", "c", "correct"], default = "correct",
                      help = "The mode, can be either 'g/generate' to generate the csv file based on the supplied images, or 'c/correct' to process the supplied images based on the csv file.") 
  parser.add_argument("-n", "--dry-run", action = "store_true",
                      help = "Don't alter any files, just print out what would be done. Only has an effect in correct mode.")
  tag_group = parser.add_mutually_exclusive_group()
  tag_group.add_argument("-i", "--ignore-reading",
                         choices = MetaDataDateTime.known_tags,
                         action = "append",
                         help = "Ignore this tag for reading the datetime (it will be included when writing though). This tag can be used multiple times.")
  parser.add_argument('csv_file', type = str, help = "The CSV file with the time samples. Its rows should contain exif and actual time seperated by a comma, both in format \"yyyy-mm-dd hh:mm:ss\". This file will be overwritten in generate mode.")
  parser.add_argument('photo', type = str, nargs = "+", help = "The photo files to use as reference images (in generate mode) or that need to be corrected (in correct mode.")
  
  args = parser.parse_args()
 
  # Check if exiftool is there
  try:
    status = subprocess.run(["exiftool", "-ver"], stdout = subprocess.PIPE)
  except FileNotFoundError:
    raise Exception("Please install Exiftool")
  if status.returncode != 0:
    raise Exception("Exiftool can't be run")

  ignore_read_tags = args.ignore_reading if args.ignore_reading else []

  if args.mode in ['g', 'generate']:
    print("What are the date en time (%s), or just time (%s) if the default date is correct, displayed on photo:" % (DT_FORMAT, TIME_FORMAT))
    dt_stamps = [getPhotoAndUserStringDT(photo, ignore_read_tags) for photo in args.photo]
    writeCSVFile(args.csv_file, dt_stamps)
  elif args.mode in ['c', 'correct']:
    reference_points = readCSVFile(args.csv_file)
    for photo in args.photo:
      processPhoto(photo, reference_points, ignore_read_tags, args.dry_run)
