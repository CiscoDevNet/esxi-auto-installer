echo -e "\E[0;36m### Listing /tftboot ###\E[0;39m"
ls -1 /tftpboot/01*
echo
echo -e "\E[0;36m### Listing kickstart dir ###\E[0;39m"
ls -1 /tftpboot/ks/*.cfg
echo
echo -e "\E[0;36m### Listing pxecfg dir ###\E[0;39m"
ls -1 /tftpboot/pxelinux.cfg/01*
echo
echo -e "\E[0;36m### Checking dhcpd config ###\E[0;39m"
sdiff /etc/dhcp/dhcpd.conf /etc/dhcp/dhcpd.conf_base
echo
ps -ef|grep dhcp
echo
