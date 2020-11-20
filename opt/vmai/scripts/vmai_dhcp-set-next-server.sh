#!/bin/bash

echo "[INFO] Running $0 script - `date +'%m.%d.%Y %T '`"
# get current IP address
#IP=`ip addr show dev ens192|awk '/inet/ {print $2}'|sed 's/\/.*//'`
IP=`awk -F"=" '/^IPADDR/ {print $2}' /etc/sysconfig/network-scripts/ifcfg-ens192`
echo "[INFO] Discovered IP addres: $IP"

# update dhcpd.conf and dhcpd.conf_base
echo "[INFO] Updating next-server in dhcpd.conf and dhcpd.conf_base"
sed -i "s/.*next-server.*/   next-server $IP\;/" /etc/dhcp/dhcpd.conf
sed -i "s/.*next-server.*/   next-server $IP\;/" /etc/dhcp/dhcpd.conf_base
echo "[INFO] Updated dhcpd configs:"
grep next-server /etc/dhcp/dhcpd.conf
grep next-server /etc/dhcp/dhcpd.conf_base
