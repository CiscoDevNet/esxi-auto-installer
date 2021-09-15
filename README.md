# ESXi Auto-Installer

ESXi Auto-Installer automates bare-metal ESXi hypervisor deployment, providing 100% hands-off installation on Cisco UCS physical servers.

## Features
- Start deployment on multiple servers in parallel (using same CIMC credentials)
- Supports custom ESXi installation ISO
- Implements most kickstart parameters described in https://docs.vmware.com/en/VMware-vSphere/6.7/com.vmware.esxi.upgrade.doc/GUID-61A14EBB-5CF3-43EE-87EF-DB8EC6D83698.html
- Supports iSCSI boot installs
- API for automation pipelines
- Future: Platform agnostic installations (including virtual machines) using PXE instead of CIMC

# Setup guide

## Pre-requisites

ESXi Auto-Installer requires Linux or “Unix-like” system with few additional components installed and 'eaiusr' account created (with full sudo rights). 
Development is done on vanilla Ubuntu 20.04.2 LTS.

### Inital Setup

``` bash
sudo git clone https://github.com/CiscoDevNet/esxi-auto-installer /opt/eai
cd /opt/eai
sudo pip install -r requirements.txt
sudo cp autoinstaller.conf /etc/httpd/config.d/
sudo echo "apache ALL=NOPASSWD:/usr/bin/mount, /usr/bin/umount, /usr/bin/mkdir, /usr/bin/chown, /usr/bin/rmdir" > /etc/sudoers.d/apache
systemctl enable apache
```

If you want to use a custom directory, see [Custom install directory](#Custom-install-directory)
### Start the application

systemctl start apache

# Usage

Point a web browser at the system where Auto-Installer running.

## First task: Upload ISO

Auto-Installer does not come bundled with an ESXi Installation ISO file. Before you can use Auto-Installer you must upload an ESXi Installation ISO file.
From the main page click on "Upload ISO" in the top menu bar.
Click Browse to locate an ISO on your local machine.
After selecting a a valid ESXi Installation ISO file, click Submit.

Now that an ISO is uploaded, you can go back to the "Home Page".

## Home page

The Home page is where you start your ESXi Installations.
In 'Step 1' is where you setup your basic installation settings.
In 'Step 2' you configure the IP settings for the ESXi hosts.

One all the correct settings have been entered, click the "START" button on the bottom to begin the installation process.
Once you click Start, you will be sent to the "Status Page".

## Status page

You can navigate to the Status Page at any time by clicking "Status" on the top menu bar.
The status page shows a history of all the installs.
You can quickly see a servers current install status in the "Status" column.
If you want to see the logs for a particular install, you can click on the link in the "Hostname" column.

## Upload ISO

You can use the Upload ISO page to upload ESXi Installation ISOs. This is useful if you need a praticular version of ESXi, or a particular installation that contains custom drivers.
Once you upload an ISO, you can select it as part of the install process on the Home Page.

## APIs

For more information on API's, see the Swagger document.

# Application Details

## Log files

Main Auto-Installer log file `eai.log` is stored under `EAILOG` and provides overview on application run and launched jobs.

'Per job ID' log files are stored in `LOGDIR` and available via web GUI ('Status' tab) or from the host system. These logs provide detailed output from all tasks executed per given job ID.

## Custom install directory

`/opt/eai` is the default directory. If you use a different directory you need to update some config files.
- the `WORKDIR` path located in the `config.py` file.
- All `/opt/eai` entries in `/etc/httpd/conf.d/autoinstaller.conf`

## Optional Configuration

All Auto-Installer configuration is stored in `config.py` file, where the following defaults can be customized:
- Main Auto-Installer directory (`WORKDIR`) and essential subdirectories
- ESXi ISO directory
- Temporary directories used during ISO upload or for storing custom installation ISO
- Toggle "dry-run", i.e. do not run any CIMC action and installation but simulate application flow
- Application status codes dictionary

## Module details

Auto-Installer is a Flask based application written in Python running behind Apache web server through mod_wsgi.
Additionaly it has the following dependencies:
- Uses Cisco IMC SDK (imcsdk Python module: https://github.com/CiscoUcs/imcsdk) for running tasks on Cisco UCS IMC
- Apache Web Server
- mod_wsgi
- Flask
