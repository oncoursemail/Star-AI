# busylog.sh OUTFILE : every 3 s, count busy live slots (star-fast, star-voice only; never query unloaded models)
K=$(head -1 /opt/star/secrets/api_keys)
while true; do b=0; for m in star-fast star-voice; do b=$((b + $(curl -s -H "Authorization: Bearer $K" "localhost:8080/slots?model=$m" | grep -o '"is_processing":true' | wc -l))); done; echo "$(date +%T) $b" >> $1; sleep 3; done
