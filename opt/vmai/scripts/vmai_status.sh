echo -e "\E[0;36m### Listing /tftboot dir ###\E[0;39m"
ls -1 /tftpboot/01*
echo
echo -e "\E[0;36m### Listing kickstart dir ###\E[0;39m"
ls -1 /tftpboot/ks/*.cfg
echo
echo -e "\E[0;36m### Listing pxecfg dir ###\E[0;39m"
ls -1 /tftpboot/pxelinux.cfg/01*
echo
echo -e "\E[0;36m### diff dhcpd.conf vs. dhcpd.conf_base ###\E[0;39m"
sdiff /etc/dhcp/dhcpd.conf /etc/dhcp/dhcpd.conf_base
echo
echo -e "\E[0;36m### Checking dhcpd service status ###\E[0;39m"
/usr/bin/systemctl status dhcpd
echo
echo -e "\E[0;36m### dhcpd process:\E[0;39m"
ps -ef|grep dhcp|grep -v grep
echo
