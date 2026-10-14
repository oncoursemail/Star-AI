K=$(head -1 /opt/star/secrets/api_keys)
for i in $(seq 1 60); do
  b=0; for m in star-fast star-voice; do b=$((b + $(curl -s -H "Authorization: Bearer $K" "localhost:8080/slots?model=$m" | grep -o '"is_processing":true' | wc -l))); done
  [ $b = 0 ] && { echo "idle at $(date +%T), load $(cut -d' ' -f1 /proc/loadavg)"; exit 0; }
  sleep 3
done; echo "still busy"; exit 1
