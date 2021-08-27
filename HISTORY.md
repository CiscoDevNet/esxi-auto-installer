History
=====================


1.0alpha (2021-07-30)
---------------------
* no PXE boot
* custom ISO is generated and mounted on target UCS machine using API call to CIMC

0.9demo (2021-01-10)
---------------------
* PXE booted installation with kickstart config
* requires Native VLAN and 'ip helper' / 'dhcp relay' set on switch
* dhcpd.conf update not validated in demo version
* configuration resdet on VM reboot
