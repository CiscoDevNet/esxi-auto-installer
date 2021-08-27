# ESXi Auto-Installer

ESXi Auto-Installer automates bare-metal ESXi hypervisor deployment, providing 100% hands-off installation on Cisco UCS physical servers ("Custom ISO" mode). Alternative deployment method - "PXE boot" mode - is platform agnostic, allowing installation on any "PXE boot capable" physical or virtual server system, however has some configuration pre-requisites on network infrastructure side. The latter is yet to be implemented.

Auto-Installer is a Flask based application written in Python running behind Apache web server through mod_wsgi.
Additionaly it has the following dependencies:
- uses IMC SDK (imcsdk Python module: https://github.com/CiscoUcs/imcsdk) for running tasks on Cisco UCS IMC
- uses DHCP server and tftpd (PXE boot mode)

## Features
- implements most kickstart parameters described in https://docs.vmware.com/en/VMware-vSphere/6.7/com.vmware.esxi.upgrade.doc/GUID-61A14EBB-5CF3-43EE-87EF-DB8EC6D83698.html
- upload and select VMware ESXi installation ISO
- start deployment on multiple servers (using same CIMC credentials) in parallel

## Support team
cll-auto-installer-support@cisco.com


# Setup guide

## Pre-requisites

ESXi Auto-Installer requires Linux or “Unix-like” system with few additional components installed and 'eaiusr' account created (with full sudo rights). Ready-to-use VM appliance (OVF template available on >>link to box folder here<<) is based on minimal installation of vanilla Ubuntu 20.04.2 LTS. To make the OVF possibly lightweight is has been installed with no X-windows system and ssh server, however default installation of Ubuntu Desktop will work as well.

### Install Auto-Installer host system pre-requisites
```
DRAFT - needs updating after clean appliance setup:
- install Apache web server
- install Python and required libraries (Flask, Flask-WTF, lxml, Jinja2, mod-wsgi, Werkzeug, ipaddress, email-validator?)
- for PXE mode there are additional system packages: dhcp-server, tftp-server
- configure sudoers for apache user:
apache ALL=NOPASSWD:/usr/bin/systemctl restart dhcpd, /usr/bin/mount, /usr/bin/umount, /usr/bin/mkdir, /usr/bin/chown, /usr/bin/rmdir
```

### Apache Virtual Host configuration
```
[root@auto-installer ~]# cat /etc/httpd/conf.d/autoinstaller.conf
<VirtualHost *:80>
     WSGIScriptAlias / /opt/eai/app/eai_flask_app.wsgi
     DocumentRoot /opt/eai
     <Directory /opt/eai/app>
            Options FollowSymLinks
            AllowOverride None
            Require all granted
     </Directory>
</VirtualHost>
```

## Prepare application environment

### Clone git repo

```
[ -d vmware-auto-installer ] && rm -rf vmware-auto-installer
git clone https://wwwin-github.cisco.com/DevCXTechEdLabTeam/vmware-auto-installer.git
```

### Copy application code to WORKDIR

Note: default `WORKDIR` path is `/opt/eai` - in case you need to change this modify `config.py` accordingly.
```
mv vmware-auto-installer /opt/eai
```


# Usage

## Configuration

All Auto-Installer configuration is stored in `config.py` file, where the following defaults can be customized:
- Main Auto-Installer directory (`WORKDIR`) and essential subdirectories
- ESXi ISO directory
- TFTPBOOT ISO directory
- Temporary directories used during ISO upload or for storing custom installation ISO
- Temporary directory for kickstart configuration files
- Kickstart and PXE configuration files templates
- Toggle "dry-run", i.e. do not run any CIMC action and installation but simulate application flow
- Application status codes dictionary


## Running the application

Once the Apache web server is started it presents Auto-Installer GUI on port :80


## Main page

Once the application is started - i.e. web server is running and presenting the application through mod_wsgi - navigate to host system IP address in web browser, port 80.

Main application page is presented, with two sections sections. 'Step 1' allows selecting hypervisor version and providing details such as ESXi root account password, management vmnic ID and VLAN, etc. 'Step 2' is split to Common Settings for all installations triggered with current run (CIMC credentials, netmask, gateway, etc.) and Unique Settings for each ESXi host (hostname, management and CIMC IP address).


## Status page

Once 'START' button is hit application redirects to 'Status' page, where all entries from Auto-Installer database are shown  reflecting current job status.


## Log files

Main Auto-Installer log file `eai.log` is stored under `EAILOG` and provides overview on application run and launched jobs.

'Per job ID' log files are stored in `LOGDIR` and available via web GUI ('Status' tab) or from the host system. These logs provide detailed output from all tasks executed per given job ID.


# API

For details on Auto-Installer API please refer to API documentation.


# TO-DO

- PXE boot mode
- API `POST /jobs` endpoint
- backend web form validation
- provide server data in CSV file
- custom kickstart text form
