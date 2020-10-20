# VMware Auto-Installer config

VMAI_DB = 'vmai_db.json'
DHCPCFG = '/etc/dhcp/dhcpd.conf'
TFTPBOOT = '/tftpboot/'
KSDIR = TFTPBOOT + 'ks/'
PXEDIR = TFTPBOOT + 'pxelinux.cfg/'
KSTEMPLATE = 'templates/kickstart_template'
PXETEMPLATE = 'templates/pxecfg_template'
DHCPTEMPLATE = 'templates/dhcp_template'
SSHTXT = """%firstboot --interpreter=busybox
# enable & start remote ESXi Shell  (SSH)
vim-cmd hostsvc/enable_ssh
vim-cmd hostsvc/start_ssh
# disable IPv6
esxcli network ip set --ipv6-enabled=false
echo "`date` - Server `hostname` installation finished." >/usr/lib/vmware/hostd/docroot/READY
sleep 30
reboot
"""
NOSSHTXT = """%firstboot --interpreter=busybox
# disable IPv6
esxcli network ip set --ipv6-enabled=false
echo "`date` - Server `hostname` installation finished." >/usr/lib/vmware/hostd/docroot/READY
sleep 30
reboot
"""

