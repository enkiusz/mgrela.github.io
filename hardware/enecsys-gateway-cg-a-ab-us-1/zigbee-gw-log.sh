#!/bin/sh

URL="$1"; shift

while true; do
	zg=$(wget -q -O - "$URL" | grep -F "<zigbeeData>" | tr -d "\r\n")
	[ "$zg" = "<zigbeeData></zigbeeData>" ] && continue
	echo "$(date --utc '+%s') $zg" >> gateway.log
done

