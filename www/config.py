# VMware Auto-Installer config
DOCROOT= '/var/www/demo/'
VMAI_DB = DOCROOT + 'vmai_db.json'
VMAI_LOG = '/opt/vmai/log/vmai.log'
DHCPCFG = '/etc/dhcp/dhcpd.conf'
TFTPBOOT = '/tftpboot/'
UPLOADDIR = DOCROOT + 'upload/'
TMPISODIR = DOCROOT + 'upload/mnt/'
TFTPISODIR = TFTPBOOT + 'iso/'
KSDIR = TFTPBOOT + 'ks/'
PXEDIR = TFTPBOOT + 'pxelinux.cfg/'
KSTEMPLATE = DOCROOT + 'templates/kickstart_template'
PXETEMPLATE = DOCROOT + 'templates/pxecfg_template'
DHCPTEMPLATE = DOCROOT + 'templates/dhcp_template'
SSHTXT = """%firstboot --interpreter=busybox
# enable & start remote ESXi Shell  (SSH)
vim-cmd hostsvc/enable_ssh
vim-cmd hostsvc/start_ssh
# disable IPv6
esxcli network ip set --ipv6-enabled=false
echo "`date` - Server `hostname` installation finished." >/usr/lib/vmware/hostd/docroot/READY
sleep 75
reboot
"""
NOSSHTXT = """%firstboot --interpreter=busybox
# disable IPv6
esxcli network ip set --ipv6-enabled=false
echo "`date` - Server `hostname` installation finished." >/usr/lib/vmware/hostd/docroot/READY
sleep 75
reboot
"""

