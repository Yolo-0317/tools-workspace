#!/bin/zsh
set -euo pipefail

project_dir="${0:A:h:h}"
source_video="$project_dir/episodes/feimei-lvyao-15s/assets/video/content-seedance-v01.mp4"
output="$project_dir/exports/feimei-lvyao-15s-repaired-v01.mp4"

[[ -s "$source_video" ]] || {
  print -u2 -r -- "Missing required input: $source_video"
  exit 1
}

mkdir -p "$project_dir/exports"

# Fixed effect timing contract:
# opening trail 0.120—1.050 s; equal pulse centres 0.420, 5.450, 11.550 s.
ffmpeg -hide_banner -loglevel error -y \
  -i "$source_video" \
  -filter_complex "\
    [0:v]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,\
      pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x172525,\
      eq=contrast=1.025:saturation=1.025:brightness=0.002,\
      unsharp=5:5:0.35:3:3:0.0,fps=24,format=yuv420p,split=2[base][pulse_src];\
    [pulse_src]eq=brightness=0.12:saturation=1.10,\
      colorchannelmixer=rr=1.08:gg=1.02:bb=0.93,gblur=sigma=12[pulse_glow];\
    [base][pulse_glow]blend=all_expr='A*(1-(0.24*max(0,1-abs(T-0.420)/0.180)+0.24*max(0,1-abs(T-5.450)/0.180)+0.24*max(0,1-abs(T-11.550)/0.180)))+B*(0.24*max(0,1-abs(T-0.420)/0.180)+0.24*max(0,1-abs(T-5.450)/0.180)+0.24*max(0,1-abs(T-11.550)/0.180))',\
      eq=brightness='0.018*(max(0,1-abs(t-0.420)/0.180)+max(0,1-abs(t-5.450)/0.180)+max(0,1-abs(t-11.550)/0.180))':eval=frame[pulsed];\
    color=c=black@0.0:s=480x80:r=24:d=1.050,format=rgba,\
      geq=r='214':g='172':b='98':a='255*0.36*exp(-pow((Y-H/2)/15,2))*sin(PI*X/W)',\
      fade=t=in:st=0.120:d=0.180:alpha=1,fade=t=out:st=0.720:d=0.330:alpha=1,\
      rotate=-0.72:c=none:ow=rotw(-0.72):oh=roth(-0.72)[trail];\
    [pulsed][trail]overlay=x='-80+(t-0.120)*360/0.930':\
      y='1400-(t-0.120)*690/0.930':enable='between(t,0.120,1.050)':\
      eof_action=pass:format=auto,format=yuv420p[vout];\
    aevalsrc='(0.62*sin(2*PI*72*t)+0.24*sin(2*PI*46*t))*exp(-7*t)':\
      s=44100:d=0.55,afade=t=out:st=0.30:d=0.25[drum];\
    anoisesrc=color=white:amplitude=0.30:sample_rate=44100:duration=0.55:seed=20260831,\
      highpass=f=900,lowpass=f=5200,afade=t=in:st=0:d=0.10,\
      afade=t=out:st=0.24:d=0.31,volume=0.18[whoosh];\
    aevalsrc='(0.18*sin(2*PI*940*t)+0.12*sin(2*PI*1410*t)+0.08*sin(2*PI*1880*t))*exp(-5*t)':\
      s=44100:d=0.70,afade=t=out:st=0.42:d=0.28[chime];\
    [drum][whoosh][chime]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0,\
      aresample=44100,aformat=channel_layouts=stereo,volume=0.38[hit];\
    [hit]asplit=3[hit1][hit2][hit3];\
    [hit1]adelay=420|420[sfx1];\
    [hit2]adelay=5450|5450[sfx2];\
    [hit3]adelay=11550|11550[sfx3];\
    [sfx1][sfx2][sfx3]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0[sfx];\
    [0:a]aresample=44100,aformat=channel_layouts=stereo[bed];\
    [bed][sfx]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,\
      alimiter=limit=0.891251:attack=5:release=80:level=false[aout]" \
  -map "[vout]" -map "[aout]" \
  -map_metadata 0 \
  -t 15.093 \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 44100 -ac 2 \
  -movflags use_metadata_tags+faststart "$output"

print -r -- "$output"
