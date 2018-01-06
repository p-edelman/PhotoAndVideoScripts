#!/bin/bash

function printUsage {
  echo "usage: $0 MOVIE DEGREES"
  echo
  echo "positional arguments:"
  echo "    MOVIE   the movie file to rotate"
  echo "    DEGREES one of 0, 90, 180, or 270"
  echo
  echo "The script sets the rotation flag of the movie file, the actual content is not changed."
  exit 1
}
  
if [ $# -ne 2 ]; then
  printUsage
fi

if [ ! -f "$1" ]; then
  printUsage
fi

case $2 in
  0|90|180|270) ;;
  *) echo "ERROR: $2 is not a valid number of degrees!"; echo; printUsage ;;
esac

# Rotating a movie is a somewhat annoying affair as we cannot directly change
# the flag with any tool, we have to 'transcode' to a new file with the changed
# flag.
# So first move the original file to a temporary file
mv "$1" "${1}_original"

# Then, run FFmpeg to create the new file. We simply copy the streams using the
# "-c copy" flag. The "-map_metadata 0" flag is needed to copy over all metadata
# from the first input file, this isn't done by default (anymore).
# To specify the rotation flag, we use the "metadata:s:v rotate=", part, which
# sets rotate to the specified value for the subtitle and video streams.
ffmpeg -i "${1}_original" -c copy -map_metadata 0 -metadata:s:v rotate="$2" -loglevel 8 "$1"

# On success, delete the temporary file
if [ $? -eq 0 ]; then
  rm "${1}_original"
else
  mv "${1}_original" "$1"
  echo "There was an error, the file wasn't changed!"
fi
