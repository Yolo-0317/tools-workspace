#!/bin/zsh
set -euo pipefail
project_dir="${0:A:h:h}"
episode="$project_dir/episodes/wangtianmenshan-15s"
build="$project_dir/scripts/build_wangtianmenshan_15s_final.sh"
output="$project_dir/exports/wangtianmenshan-15s-subtitled-v01.mp4"
[[ -s "$episode/assets/video/content-seedance-v01.mp4" ]] || { print -u2 "FAIL: missing source video"; exit 1; }
[[ -s "$episode/voice-lines.json" ]] || { print -u2 "FAIL: missing voice-lines.json"; exit 1; }
[[ -s "$episode/subtitle-plan.json" ]] || { print -u2 "FAIL: missing subtitle-plan.json"; exit 1; }
[[ -x "$build" ]] || { print -u2 "FAIL: missing executable build script"; exit 1; }
jq -e '.episode=="wangtianmenshan-15s" and [.lines[].role]==["zhixia","zhixia","zhixia","zhixia"] and [.lines[].text]==["天门中断楚江开。","碧水东流至此回。","两岸青山相对出。","孤帆一片日边来。"]' "$episode/voice-lines.json" >/dev/null
jq -e 'length==4 and .[0].attribution=="唐·李白" and .[0].start<=0.5 and .[3].end>=14.0 and .[3].end<=14.6 and .[0].end+0.7<=.[1].start and .[1].end+0.7<=.[2].start and .[2].end+0.7<=.[3].start' "$episode/subtitle-plan.json" >/dev/null
"$build" >/dev/null
[[ -s "$output" ]] || { print -u2 "FAIL: missing final video"; exit 1; }
probe="$(ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,sample_rate,channels -show_entries format=duration -of json "$output")"
print -r -- "$probe" | jq -e '(.streams|map(select(.codec_name=="h264" and .width==1080 and .height==1920 and .r_frame_rate=="24/1"))|length)==1 and (.streams|map(select(.codec_name=="aac" and .sample_rate=="48000" and .channels==2))|length)==1 and (.format.duration|tonumber)>=15 and (.format.duration|tonumber)<=15.2' >/dev/null
print "PASS: Wangtianmenshan 15s final is ready"
