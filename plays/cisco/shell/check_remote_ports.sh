
for r in /sys/class/fc_remote_ports/rport-*; do
  echo "== $(basename "$r") =="
  echo "remote WWPN: $(cat "$r/port_name" 2>/dev/null)"
  echo "remote WWNN: $(cat "$r/node_name" 2>/dev/null)"
  echo "state:       $(cat "$r/port_state" 2>/dev/null)"
  echo "roles:       $(cat "$r/roles" 2>/dev/null)"
  echo
done
