History
=====================
2.4 (2023-11-08)
---------------------
* Fix: cleanup after failed ISO upload
* Fix: progress bar visibility
* Added message after saving ISO while waiting on backend functions to finish extracting files and preparing tftpboot

2.3 (2023-11-01)
---------------------
* Added progress indicator on /upload page

2.2 (2022-12-19)
---------------------
* Make installer compatible with Secure Boot. Added additional status update when installer starts.

2.1 (2022-11-28)
---------------------
* removed EAIDB file from repo and added check/create script before starting containers

2.0 (2022-11-10)
---------------------
* Added PXE boot installation method

1.5 (2022-01-27)
---------------------
* Additional status when hypervisor has been installed and server goes for the First Boot

1.4 (2022-01-27)
---------------------
* Return an error on API /jobs POST call when ISO not found

1.3 (2022-01-18)
---------------------
* Use Ubuntu and Nginx Docker containers instead of Apache + mod_wsgi Linux setup

1.2 (2021-12-03)
---------------------
* use http instead of https when port 80 is provided in CIMC IP address

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
