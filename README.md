# Photo and video scripts

A collection of useful scripts to manipulate photo and video files

## telltimeadjustment.py

A script that let's you figure out the offset of the camera clock. It works by taking a picture of a second-accurate clock and comparing that to the EXIF time.

This is especially useful if you want to correlate images with a GPS track, since second-accuracy is required to find the best match.

### Requirements

- Python3
- Exiftool

### Usage

First, take a picture of a second-accurate clock (a GPS, a computer synced by NTP, etc.) with the camera you want to know about. Download the picture and write down the time you see on it in the format HH:MM:SS

Then, run:

    telltimeadjustment.py IMAGE_FILE TIMESTAMP

The result will be the offset off the camera to the actual time.

## correctphotodrift.py

Continuation of ```telltimeadjustment.py``` that corrects the date and time in a bunch of photo files based on a list of reference images.

Camera clocks tend to drift over time (quite a bit, I've noticed) so if you have a photo project that spans multiple days, it's better to work with multiple reference photos. Unfortunately, the drift isn't exactly linear, so the more reference photos, the better.

This script uses a list of reference timestamps to figure out how the time on each photo should be adjusted, and applies this adjustment. A simple interpolation between reference timestamps is used (or for photo on the edges, between the two closest timestamps).

## Requirements

- Python3
- Exiftool

### Usage

First, create reference photos by taking pictures of a second-accurate clock (a GPS, a computer synced by NTP, etc.)

Second, create a .csv file, where each line consists of:

- the exif datetime (use ```exiftool -CreateDate``` to find out)
- a comma
- the actual datetime (the time shown on the photo)
- all in the format YYYY-MM-DD HH:MM:SS

For example, create a file called ```camera.csv``` containing the lines:

    2017-10-21 10:55:58,2017-10-21 11:03:25
    2017-10-24 08:27:07,2017-10-24 08:34:41
    2017-10-25 13:12:26,2017-10-25 13:20:03
    2017-10-26 05:42:29,2017-10-26 05:50:08
    2017-10-29 17:15:46,2017-10-29 17:23:35

Then, run the script:

    correctphotodrift -c csv_file photo_files
    
The script will correct the time on each photo and print out the result. The original files will be saved with ```_original``` appended to the file name (this is default behavior for Exiftool). You might want to delete these original files afterwards.

## stabilizevideo.sh

A wrapper script for stabilizing video's using the vidstab plugin for FFmpeg.

Stabilization using this plugin is done in two passes. In the first pass, the video is analyzed for movements, in the second pass a stabilized copy of the video is produced. This script combines the two passes and can be fed a bunch of files. In addition, it can deinterlace files and write out a script to tranform the input video to the output.

The movement analysis file (the .trf file) will be retained and reused on a second run (unless you use the ```-ignore-trf``` option).

### Requirements

- FFmpeg
- The vidstab plugin for FFmpeg
- Bash
- Exiftool

### Usage

    USAGE: stabilizevideo.sh [options] FILE1 [FILE2 FILE3]

    Where options are:
    -s, --shakiness=SHAKINESS 
                 The shakiness or quickness of the camera in the input video. This
                 parameter corresponds to the "shakiness" parameter of the
                 vidstabdetect filter. If you run this script a second time with a
                 modified shakiness parameter, you need to delete the .trf file 
                 first.
    -a, --averaging=AVERAGING
                 The number of frames to average over during the output pass. It
                 corresponds to the "smoothing" parameter of the vidstabtransform
                 filter.
    -o, --optzoom=OPTZOOM
                 Zooming strategy to avoid black borders.
                   0 = disabled, black borders are shown.
                   1 = static zoom, only strong movements result in borders.
                   2 = dynamic zoom, no borders are visible.
    ---deinterlace
                 Deinterlace the video before stabilizing it. The shakiness
                 detection doesn't work very well on interlaced videos.
    --overwrite-trf
                 Overwrite previously generated .trf file.
    --script
                 Write out a bash script to reproduce the steps to transform the
                 input video file to the output video file. It has the same file  
                 name as the input video.
                 NOTE: If there already is a .trf file, the creation of this file is
                       omitted from the script as well.
    --from=TIMESTAMP
    --to=TIMESTAMP
                 Process only the specified part of the video.
    -h, --help
                 Print out this help and exit.

## grabframe.py

Save single frames from a video to jpg file, with the correct timestamp

### Requirements

- Python3
- FFmpeg
- Exiftool

### Usage

    grabframe.py VIDEO_FILE TIMESTAMP1 [TIMESTAMP2 TIMESTAMP3 ...]
    
The time stamps can be formatted in [HH]:MM:SS.[sss] format, with the minutes and second specified with one or two digits. The hours and subseconds are optional.

Alternatively, the number of seconds and optionally subseconds can be used.

The files will be saved under the name of the video file combined with sequence number
