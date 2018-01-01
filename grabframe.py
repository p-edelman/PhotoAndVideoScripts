#!/usr/bin/env python3

import os.path, re, subprocess, sys
   
class TimeFormat:
  """ Class for storing and converting timestamps. """
  
  class TimeFormatException(Exception):
    pass
  
  def __init__(self, time_stamp):
    """ Initialize with a time stamp in [HH]:MM:SS[.sss] or SS[.sss] format.
        If the time stamp can't be parsed, a TimeFormatExecption is raised. """
    self._original_str = time_stamp
    
    # Match hours, minutes, seconds and subseconds
    match = re.match("^([0-9]+:)??([0-9]{1,2}:)?([0-9]+)(\.[0-9]+)?$", time_stamp)
    if match:
      h = 0 if not match.group(1) else int(match.group(1)[:-1])
      m = 0 if not match.group(2) else int(match.group(2)[:-1])
      s = int(match.group(3))
      
      # Store subseconds as string, because it's more accute than a float and we
      # always need to convert it back to a string anyway
      self.s_sub = match.group(4)
      
      # Sanity checks
      if m > 59:
        raise TimeFormat.TimeFormatException("Minutes notition wrong in \"%s\"" % time_stamp)
      if (h > 0 or m > 0) and (s > 59):
        raise TimeFormat.TimeFormatException("Seconds notition wrong in \"%s\"" % time_stamp)
      
      # Store the rest of the time as the number of seconds
      self.s = s + (m * 60) + (h * 60 * 60)
      
    else:
      raise TimeFormat.TimeFormatException("Unrecognized time format: %s" % time_stamp)

  def getOriginal(self):
    """ Return the original time stamp string. """
    
    return self._original_str
    
  def getSecFormat(self):
    """ Return the timestamp formatted as SS.sss """
    
    ret_str = "%s" % self.s
    if self.s_sub:
      ret_str += "%s" % self.s_sub
    
    return ret_str
  
  def getHMSFormat(self):
    """ Return the timestamp formatted as HH:MM:SS """
    
    # Convert to hours, minutes, seconds
    seconds = self.s
    hours = seconds / (60 * 60)
    seconds = seconds % (60 * 60)
    minutes = seconds / 60
    seconds = seconds % 60
    
    # Round subseconds to nearest second
    if float(self.s_sub) >= 0.5:
      seconds += 1
    
    ret_str = "%02d:%02d:%02d" % (hours, minutes, seconds)
    
    return ret_str
    
class JPGFileNameGenerator:
  """ Class for generating unique jpg file names using a sequence number that is
      appended to the base name of the input video file. """
  
  def __init__(self, reference_path):
    self.base = os.path.splitext(reference_path)[0]
    self.seq = 0
  
  def get(self):
    candidate = "%s_%03d.jpg" % (self.base, self.seq)
    while os.path.exists(candidate):
      self.seq += 1
      candidate = "%s_%03d.jpg" % (self.base, self.seq)
    
    return candidate
  
def showHelp():
  print("Save a frames from a video file to jpg with the correct timestamp")
  print("\nUSAGE: %s VIDEO_FILE TIMESTAMP1 [TIMESTAMP2 TIMESTAMP3 ...]" % sys.argv[0])
  print("Where time stamps can be formatted as [HH:]MM:SS[.sss] or SS[.sss] format (with one or two digits for the HH, MM and SS fields, and optional hour and subsecond fields.)")
  print("\nThe files will be saved under the name of the video file combined with sequence number")
  sys.exit(1)
  
if __name__ == "__main__":
  if len(sys.argv) < 3:
    showHelp()
  
  # Check if FFmpeg and Exiftool are installed
  try:
    subprocess.run(["ffmpeg", "-version"], stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
  except FileNotFoundError:
    sys.stdout.write("The required FFmpeg program is missing")
    sys.exit(1)
  try:
    subprocess.run(["exiftool", "-ver", "-q"], stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
  except FileNotFoundError:
    sys.stdout.write("The required Exiftool program is missing")
    sys.exit(1)
  
  # Check if the video file is there
  video_file = sys.argv[1]
  if not (os.path.exists(video_file) and os.path.isfile(video_file)):
    sys.stderr.write("ERROR: file \"%s\" does not exist" % video_file)
    showHelp()
  
  # Collect all time stamps
  stamps = []
  for time_stamp in sys.argv[2:]:
    try:
      stamps.append(TimeFormat(time_stamp))
    except TimeFormat.TimeFormatException as e:
      sys.stdout.write("ERROR: %s\n\n" % str(e))
      showHelp()
  
  # Process all time stamps
  generator = JPGFileNameGenerator(video_file)
  for stamp in stamps:
    file_name = generator.get()
    
    # Cut out the frame
    ffmpeg_params = [
      "ffmpeg",
      "-ss", stamp.getSecFormat(), # Seek the input to the specified time stamp
      "-accurate_seek",            # Don't round to the closes seek point, we want the exact frame
      "-i", video_file,
      "-frames:v", "1",            # We want a single vide frame
      "-loglevel", "24",           # Log at warning level, since that is where critical errors for creating the jpg are reported
      file_name]
    ffmpeg_result = subprocess.run(ffmpeg_params, stderr = subprocess.PIPE)
    
    # FFmpeg does not throw a fatal error or exit with a non-zero return code
    # when the operation fails, so we have to check for the existence of the
    # jpg file to determine success.
    if not os.path.exists(file_name):
      sys.stderr.write("It seems like the operation failed for timestamp \"%s\"! " % stamp.getOriginal())
      sys.stderr.write("Here's the output of FFmpeg:\n=====\n%s\n=====\n" % ffmpeg_result.stderr.decode("utf-8"))
    else:
      print("Time stamp \"%s\" is saved as \"%s\"" % (stamp.getOriginal(), file_name))
      
      # Copy the video metadata to the jpeg file
      exiftool_copy_params = [
        "exiftool",
        "-q",
        "-overwrite_original",
        "-tagsfromfile", video_file,
        file_name]
      exiftool_copy_result = subprocess.run(exiftool_copy_params)
      if exiftool_copy_result.returncode != 0:
        sys.stderr.write("Couldn't copy the metadata!")
      else:
        # Shift the time stamp to the point where the frame was grabbed
        exiftool_shift_params = [
          "exiftool",
          "-q",
          "-overwrite_original",
          "-alldates+=%s" % stamp.getHMSFormat(),
          file_name]
        exiftool_shift_result = subprocess.run(exiftool_shift_params)
        if exiftool_shift_result.returncode != 0:
          sys.stderr("Couldn't update the time stamp!")
