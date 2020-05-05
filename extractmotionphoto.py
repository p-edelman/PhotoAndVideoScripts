#!/usr/bin/env python3

import argparse, os, re, subprocess, sys

def failWithMessage(message):
    print(message)
    sys.exit(1)

if __name__ == "__main__":
    # Build a parser and parse the command line
    parser = argparse.ArgumentParser(description = "Extract the	 embedded video from a Samsung Motion Photo.")
    parser.add_argument("-s", "--split", action = "store_true",
                        help = "Split the files, that is, remove the embedded video from the jpg file as well. WARNING: use at your own risk - it might be a good idea to make a backup first.")
    parser.add_argument("jpg_file", type = str, help = "The photo file that should contain the embedded video")
    args = parser.parse_args()
 
    # Check if exiftool is there
    try:
        status = subprocess.run(["exiftool", "-ver"], stdout = subprocess.PIPE)
    except FileNotFoundError:
        failWithMessage("Please install Exiftool")
    if status.returncode != 0:
        failWithMessage("Exiftool can't be run")

    if not os.path.exists(args.jpg_file):
        failWithMessage("Photo file %s does not exist" % args.jpg_file)

    # Check the EmbeddedVideoType flag, should be "MotionPhoto_Data" for Samsung
    # Motion Photos
    result = subprocess.run(["exiftool", "-S", "-EmbeddedVideoType", args.jpg_file], stdout = subprocess.PIPE)
    if result.returncode != 0:
        failWithMessage("Exiftool failed on %s" % args.jpg_file)
    stdout = result.stdout.decode("utf-8").split(":")
    if len(stdout) != 2 or stdout[1].strip() != "MotionPhoto_Data":
        failWithMessage("'%s' is probably not a Samsung Motion Photo" % args.jpg_file)
    
    # If we're good, extract the embedded video and copy the metadata
    base, _ = os.path.splitext(args.jpg_file)
    result = subprocess.run(["exiftool", "-b", "-EmbeddedVideoFile", args.jpg_file], stdout = subprocess.PIPE)
    if result.returncode != 0:
        failWithMessage("Couldn't extract the embedded video")
    else:
        with open(base + ".mp4", "wb") as mp4:
            mp4.write(result.stdout)
        print("Embedded video saved as '%s.mp4'" % base)
        result_metadata = subprocess.run(["exiftool", "-overwrite_original", "-tagsfromfile", args.jpg_file, base + ".mp4"], stdout = subprocess.PIPE)
        if result_metadata.returncode != 0:
            print("Warning: couldn't copy metadata to mp4 file")

    if args.split:
        # The embedded video is basically pasted to the end of the jpg file, so
        # removing it basically means cutting the tail off the jpg file. Let's
        # ask Exiftool where we should cut.
        # NOTE: we could use this same mechanism to extract the video, but it's
        #       a bit safer to just use Exiftool for this.
        result = subprocess.run(["exiftool", "-v1", args.jpg_file], stdout = subprocess.PIPE)
        if result.returncode != 0:
            failWithMessage("Couldn't remove the embedded video")
        stdout = result.stdout.decode("UTF-8")

        # Do a sanity check to see if there's only an embedded video in the JPG
        # trailer
        offset = None
        in_samsung_section = False
        for line in stdout.split("\n"):
            if not in_samsung_section and line.startswith("Samsung trailer"):
                in_samsung_section = True

                # While we're here, extract the offset of the Samsung trailer                
                offset_match = re.search("Samsung trailer \(\d+ bytes at offset (0x[\da-f]+)", line)
                if offset_match:
                    offset = offset_match.group(1)
                else:
                    failWithMessage("Couldn't remove the embedded video")

            elif in_samsung_section:
                if line.startswith("  "):
                    if not re.match("  (Samsung_Trailer|TimeStamp|SamsungTrailer|EmbeddedVideo)", line):
                        failWithMessage("Unknown content found in Samsung portion of the file. Embedded video couldn't be removed")
                else:
                    in_samsung_section = False

        if offset == None:
            failWithMessage("Couldn't remove the embedded video")

        # Save a trunctated version of the jpg file up to the offset
        with open(args.jpg_file, "rb") as jpg_file:
            jpg_data = jpg_file.read(int(offset, 16))
        with open(args.jpg_file, "wb") as jpg_file:
            jpg_file.write(jpg_data)
