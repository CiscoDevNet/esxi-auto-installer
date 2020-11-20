echo "[INFO] Running $0 script - `date +'%m.%d.%Y %T '`"


echo -e "\E[0;36m### Cleanup /tftboot ###\E[0;39m"
rm -rf /tftpboot/01*
ls -1 /tftpboot/01*
echo
echo -e "\E[0;36m### Cleanup kickstart dir ###\E[0;39m"
rm -f /tftpboot/ks/*.cfg
ls -1 /tftpboot/ks/*.cfg
echo
echo -e "\E[0;36m### Cleanup pxecfg dir ###\E[0;39m"
rm -f /tftpboot/pxelinux.cfg/01*
ls -1 /tftpboot/pxelinux.cfg/01*
echo
echo -e "\E[0;36m### Restore vanilla dhcpd.conf ###\E[0;39m"
cp /etc/dhcp/dhcpd.conf_base /etc/dhcp/dhcpd.conf
chown apache /etc/dhcp/dhcpd.conf
ls -l /etc/dhcp/dhcpd.conf
ls -l /etc/dhcp/dhcpd.conf_base
echo
echo -e "\E[0;36m### Clean vmai_db.json ###\E[0;39m"
echo -e "{\n}" >/var/www/demo/vmai_db.json
cat /var/www/demo/vmai_db.json
