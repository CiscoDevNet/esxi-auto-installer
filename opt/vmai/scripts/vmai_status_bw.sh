# monochromatic output for better display in web gui
echo
echo -e "### Listing /tftboot dir ###"
ls -1 /tftpboot/01*
echo
echo -e "### Listing kickstart dir ###"
ls -1 /tftpboot/ks/*.cfg
echo
echo -e "### Listing pxecfg dir ###"
ls -1 /tftpboot/pxelinux.cfg/01*
echo
echo -e "### diff dhcpd.conf vs. dhcpd.conf_base ###"
sdiff /etc/dhcp/dhcpd.conf /etc/dhcp/dhcpd.conf_base
echo
echo -e "### Checking dhcpd service status ###"
/usr/bin/systemctl status dhcpd
echo
echo -e "### dhcpd process:"
ps -ef|grep dhcp|grep -v grep
echo
