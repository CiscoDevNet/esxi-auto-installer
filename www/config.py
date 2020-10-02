# VMware Auto-Installer config

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
reboot
"""

