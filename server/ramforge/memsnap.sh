# memsnap.sh : RSS per live model process + container memory
for p in $(pgrep -f -- "/opt/star/bin.*/llama-server.*--alias"); do
  a=$(tr '\0' ' ' < /proc/$p/cmdline | grep -o -- "--alias [^ ]*" | cut -d' ' -f2)
  echo "rss_mib $a $(( $(awk '/VmRSS/{print $2}' /proc/$p/status) / 1024 )) bin=$(readlink /proc/$p/exe)"
done
free -m | awk '/Mem:/{print "mem_used_mib", $3, "available_mib", $7}'
