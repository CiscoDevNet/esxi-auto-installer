History
=====================

1.3 (2022-01-18)
---------------------
* Use Ubuntu and Nginx Docker containers instead of Apache + mod_wsgi Linux setup

1.1 (2021-11-09)
---------------------
* SHA512 hashed root password in kickstart file

1.0 (2021-10-29)
---------------------
* set vmedia as one-time-boot-device or first device in boot order

1.0alpha13 (2021-10-18)
---------------------
* added Welcome Page when there is no installation ISO

1.0alpha12 (2021-10-18)
---------------------
* changed how EAI_HOST_IP is set

1.0alpha11 (2021-10-15)
---------------------
* added eaidb_remove_cimc_password() to cleanup procedure

1.0alpha10 (2021-10-11)
---------------------
* cimc_unmount_iso unmounts only the ISO related to specific job ID
* job_cleanup - added unmount_iso boolean so that we can skip unmounting when we got CIMC authentiocation error
* removed get_main_logger() call from function declarations

1.0alpha9 (2021-10-01)
---------------------
* rebuilt API with flask_restful
* added API POST /jobs and GET /isos

1.0alpha8 (2021-09-24)
---------------------
* moved KickStart and ISO generation into it's own subprocess
* added DNS fields to home page

1.0alpha7 (2021-09-20)
---------------------
* hide passwords in web form
* styles cleanup
* removed PXE boot related files

1.0alpha6 (2021-09-17)
---------------------
* Included Swagger documentation.

1.0alpha5 (2021-09-13)
---------------------
* removed root password when saving kickstart to job log
* removed Cisco logo
* removed 'Upload a CSV file' option (not implemented yet)

1.0alpha4 (2021-09-07)
---------------------
* removed disabling IPv6 and final reboot from kickstart template

1.0alpha3 (2021-08-30)
---------------------
* CIMC address allowing custom port (ip[:port])

1.0alpha (2021-07-30)
---------------------
* no PXE boot
* custom ISO is generated and mounted on target UCS machine using API call to CIMC

0.9demo (2021-01-10)
---------------------
* PXE booted installation with kickstart config
* requires Native VLAN and 'ip helper' / 'dhcp relay' set on switch
* dhcpd.conf update not validated in demo version
* configuration reset on VM reboot
