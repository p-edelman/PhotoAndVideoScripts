#!/bin/bash

# Defaults
SHAKINESS=5
SMOOTHING=10
OPTZOOM=1
GENERATETRF=0
DEINTERLACE=0
EMITSCRIPT=0
SCRIPTFILE=""
FROM=""
TO=""

function show_help() {
  echo "USAGE: $0 [options] FILE1 [FILE2 FILE3]"
  echo "
Where options are:"
  echo "-s, --shakiness=SHAKINESS 
             The shakiness or quickness of the camera in the input video. This
             parameter corresponds to the \"shakiness\" parameter of the
             vidstabdetect filter. If you run this script a second time with a
             modified shakiness parameter, you need to delete the .trf file 
             first."
  echo "-a, --averaging=AVERAGING
             The number of frames to average over during the output pass. It
             corresponds to the \"smoothing\" parameter of the vidstabtransform
             filter."
  echo "-o, --optzoom=OPTZOOM
             Zooming strategy to avoid black borders.
               0 = disabled, black borders are shown.
               1 = static zoom, only strong movements result in borders.
               2 = dynamic zoom, no borders are visible."
  echo "---deinterlace
             Deinterlace the video before stabilizing it. The shakiness
             detection doesn't work very well on interlaced videos."
  echo "--ignore-trf
             Ignore previously generated .trf file."
  echo "--script
             Write out a bash script to reproduce the steps to transform the
             input video file to the output video file. It has the same file  
             name as the input video.
             NOTE: If there already is a .trf file, the creation of this file is
                   omitted from the script as well."
  echo "--from=TIMESTAMP
--to=TIMESTAMP
             Process only the specified part of the video."
  echo "-h, --help
             Print out this help and exit."
  exit 1
}

function execute() {
  # Execute the given command. If we need to emit a script, the command is also
  # appended to the script.
  
  # Run the command
  $1
  
  # Write it to the script, if needed
  if [[ ! -z $SCRIPTFILE ]]; then
    echo $1 >> $SCRIPTFILE
  fi
}

if ! OPTIONS=$(getopt -u -o s:a:o:h -l shakiness:,averaging:,optzoom:,deinterlace,ignore-trf,script,from:,top: -- "$@")
then
  exit 1
fi

set -- $OPTIONS

while [ $# -gt 0 ]
do
  case $1 in
    -s|--shakiness) SHAKINESS="$2"; shift ;;
    -a|--averaging) SMOOTHING="$2"; shift ;;
    -o|--optzoom)   OPTZOOM="$2";   shift ;;
    --deinterlace)  DEINTERLACE=1;;
    --ignore-trf)   GENERATETRF=1;;
    --script)       EMITSCRIPT=1;;
    --from)         FROM="-ss $2 "; shift;;
    --top)          TO="-to $2 ";    shift;;
    -h| --help)     show_help;;
    (--) shift; break;;
    (*) break;;
  esac
  shift
done

# Check if we have any arguments, and if not, display some help
if [ "$#" -eq 0 ]; then
  show_help
fi

# Process all FILEs
for FILE in "$@"; do
  BASE="${FILE%.*}"
  EXT="${FILE##*.}"

  if [[ $BASE == *"_vidstab" ]]; then
    echo "$FILE is already stabilized, skipping"
    BASE=""
  fi
  
  if [ "$BASE" != "" ]; then
    echo "###### Processing $BASE.$EXT ######"

    if [ $EMITSCRIPT == 1 ]; then
      SCRIPTFILE="${BASE}.sh"
      echo "#!/bin/bash" > $SCRIPTFILE
      chmod 755 $SCRIPTFILE
    fi
    
    if [ $DEINTERLACE == 1 ]; then
      echo "- creating deinterlaced copy"
      WORKING_FILE="$BASE"_deint.mp4
      execute "ffmpeg -loglevel 8 ${FROM}-i ${FILE} ${TO}-vf yadif -c:v libx264 -crf 0 -acodec copy ${WORKING_FILE}"
    else
      WORKING_FILE="$FILE"
    fi

    if [ ! -e "$FILE".trf ]; then
      GENERATETRF=1
    fi
    
    if [ $GENERATETRF == 1 ]; then
      echo "- creating stabilization file"
      execute "ffmpeg -loglevel 8 ${FROM}-i ${WORKING_FILE} ${TO}-vf vidstabdetect=result=${FILE}.trf:accuracy=15:shakiness=${SHAKINESS} -f null -"
    else
      echo "- using existing stabilization file"
    fi
 
    echo "- creating new video file"
    execute "ffmpeg -loglevel 8 ${FROM}-i ${WORKING_FILE} ${TO}-vf vidstabtransform=input=${FILE}.trf:optzoom=$OPTZOOM:interpol=3:smoothing=${SMOOTHING} ${BASE}_vidstab.mp4"
    
    echo "- copying metadata"
    execute "exiftool -q -tagsfromfile ${FILE} ${BASE}_vidstab.mp4"
    execute "rm ${BASE}_vidstab.mp4_original"
    
    if [ $DEINTERLACE == 1 ]; then
      echo "- removing deinterlaced copy"
      execute "rm ${WORKING_FILE}"
    fi
    
    echo "- Done! The new file is called ${BASE}_vidstab.mp4"
  fi
done
