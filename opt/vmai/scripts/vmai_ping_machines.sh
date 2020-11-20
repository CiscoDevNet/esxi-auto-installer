while [ 1 ]
do
  echo
  for SRV in `awk '/fixed-address/ {print $2}' /etc/dhcp/dhcpd.conf|sed 's/\;//g'`
  do
    ping -c1 -t1 $SRV >/dev/null 2>&1
    [ $? -ne 0 ] && echo -e "\E[1;31mServer $SRV is DOWN...\E[0;39m" || echo -e "\E[0;32mServer $SRV is UP!\E[0;39m"
  done
  sleep 10
done
