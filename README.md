# ESXi Auto-Installer

ESXi Auto-Installer automates bare-metal ESXi hypervisor deployment, providing 100% hands-off installation on Cisco UCS physical servers.

ESXi Auto-Installer will:
- Install the ESXi Operating System on a Cisco Server.
- Configure the ESXi Management interface with an IP address.
- Enable SSH

After Auto-Installer is complete, you can use your traditional automation methods to configure the ESXi Host.

## Features
- Start deployment on multiple servers in parallel (using same CIMC credentials)
- Supports custom ESXi installation ISO
- Implements most kickstart parameters described in [VMWare's documentation](https://docs.vmware.com/en/VMware-vSphere/7.0/com.vmware.esxi.upgrade.doc/GUID-61A14EBB-5CF3-43EE-87EF-DB8EC6D83698.html)
- Supports iSCSI boot installs
- [API for additional automation](https://ciscodevnet.github.io/esxi-auto-installer/)
- Future: Platform agnostic installations (including virtual machines) using PXE boot

# Setup guide

## Pre-requisites

ESXi Auto-Installer requires Linux or “Unix-like” system with few additional components installed.\
These install instructions were created using Ubuntu 20.04.2 LTS.

## Initial Setup

``` bash
sudo apt update
sudo apt install git ca-certificates curl gnupg lsb-release -y

# Install Docker Engine
# Follow steps described on https://docs.docker.com/engine/install/
# Example code for Ubuntu:
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io -y

# Install Docker Compose
# Follow steps described on https://docs.docker.com/compose/install/
# Example code for Ubuntu:
sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# get the latest ESXi Auto-Installer code
sudo git clone https://github.com/CiscoDevNet/esxi-auto-installer /opt/eai

# start the application
cd /opt/eai/auto-installer_docker
sudo ./run_docker.sh 
```

If you want to use a custom directory, see [Custom install directory](#Custom-install-directory)

# Usage

Point a web browser at the system where ESXi Auto-Installer running.

## First task: Upload ISO

Auto-Installer does not come bundled with an ESXi Installation ISO file. Before you can use ESXi Auto-Installer you must upload an ESXi Installation ISO file.\
From the main page click on "Upload ISO" in the top menu bar.\
Click Browse to locate an ISO on your local machine.\
After selecting a valid ESXi Installation ISO file, click Submit.

Now that an ISO is uploaded, you can go back to the "Home Page".

## Home page

![Home Page](doc_images/home.png)\
The Home page is where you start your ESXi Installations.\
In 'Step 1' is where you setup your basic installation settings.\
In 'Step 2' you configure the IP settings for the ESXi hosts.

Once all the correct settings have been entered, click the "START" button on the bottom to begin the installation process.\
Once you click Start, you will be sent to the "Status Page".

## Status page

![Status Page](doc_images/status.png)\
You can navigate to the Status Page at any time by clicking "Status" on the top menu bar.\
The status page shows a history of all the installs.\
You can quickly see a server's current install status in the "Status" column.\
If you want to see the logs for a particular install, you can click on the link in the "Hostname" column.

## Upload ISO page

![Upload ISO Page](doc_images/uploadiso.png)\
You can use the Upload ISO page to upload ESXi Installation ISOs. This is useful if you need a particular version of ESXi, or an ISO that contains custom drivers.\
Once you upload an ISO, you can select it as part of the install process on the Home Page.

## API page

![API Page](doc_images/api.png)\
The API page shows the Swagger documentation for the APIs. You do not have to authenticate to use the APIs.

You can also view the [Swagger Document in on Git](https://ciscodevnet.github.io/esxi-auto-installer/).

### Ansible Example
An example Ansible Playbook that installs ESXi using the CIMC method via the APIs is included in this repo.\
To run the Ansible Playbook example, download the [ansible-cimc-playbook.yml](ansible-cimc-playbook.yml) and [ansible-cimc-inventory.yml](ansible-cimc-inventory.yml) files.
Edit the `ansible-cimc-inventory.yml` file and put your server(s) information in place of the example values.\
Then run:
``` bash
ansible-playbook -i ansible-cimc-inventory.yml ansible-cimc-playbook.yml
```

# Application Details

## Log files

The main ESXi Auto-Installer log file `eai.log` is stored under `EAILOG` and provides overview on application run and launched jobs.

'Per job ID' log files are stored in `LOGDIR` directory and available via web GUI ('Status' tab) or from the host system. These logs provide detailed output from all tasks executed per given job ID.

## Custom install directory
`/opt/eai` is the default directory. If you use a different directory, you need to update some config files.
- the `WORKDIR` path located in the `config.py` file.
- All `/opt/eai` references in the following files:
```
./auto-installer_docker/run_docker.sh
./auto-installer_docker/nginx/project.conf
./auto-installer_docker/docker-compose.yml
./auto-installer_docker/auto-installer_flask/Dockerfile
```

## Optional Configuration

Auto-Installer Flask application configuration is stored in `config.py` file, where the following defaults can be customized:
- Main ESXi Auto-Installer directory (`WORKDIR`) and essential subdirectories
- ESXi ISO directory
- Temporary directories used during ISO upload or for storing custom installation ISO
- Toggle "dry-run", i.e. do not run any CIMC action or installation but simulate application flow
- Application status codes dictionary

## Module details

Auto-Installer is a [Flask](https://flask.palletsprojects.com) based application written in Python running in Ubuntu [Docker](https://www.docker.com/) container behind nginx container web proxy. Ubuntu Docker image has been used instead of official Python image as the latter is missing genisoimage command EFI related flags.
Additionally, it uses [Python SDK for Cisco IMC](https://github.com/CiscoUcs/imcsdk) for running tasks on Cisco UCS IMC.

## Common issues

### My server reboots, but does not install ESXi.
ESXi Auto-Installer mounts the ESXi ISO to your Cisco server via IMC. But after it reboots your server, it's up to the server's boot order to decide whether or not the server will boot off the Virtual DVD Drive.
Your Cisco server's Boot Order can be set to 'basic mode' or 'advanced mode'.\
If the server is in 'basic mode', ensure that CDROM boot option is near the top, usually before the HDD and PXE boot options.\
If the server is in 'advanced mode', you want VMEDIA to be near the top. You can also use the 'one time boot' option to boot to VMEDIA if it is not near the top.

### ESXi hosts status does not change to finished.
The kickstart file instructs the host to contact the Auto-Installer via the /api/v1/jobs PUT API to update its status to "Finished".\
If the ESXi host installed successfully, but the status on Auto-Installer did not update to "Finished", it could be because the ESXi host was unable to contact the Auto-Installer during the initial ESXi boot.

Common reasons are wrong IP Address, Gateway, VLAN or VMNIC settings. Or the ESXi host may require a static route.
If the ESXi host is in an isolated network and there is no way for it to contact the Auto-Installer, then it cannot update the status to finished.

### I saw warnings on the ESXi Console during the installation phase!
It is normal to see warnings on the ESXi Console screen during the installation phase.\
As long as they are **warnings** and not **errors**, the installation will continue.\
There may also be prompts that say "Press ENTER to contiue". But it is recommended that you do not press any keys. Again, as long there are no actual errors, the installation will continue and the warning/prompt will go away momentarially.

### There is a problem with the kickstart file, how do I troubleshoot it?
If you get the error similar to:
![Kickstart Error](doc_images/kickstarterror.png)
```
An error has occurred while parsing the installation script

error:/vmfs/volumes/mpx.vmhba32:c0:t0:l3/KS.CFG:line
```
Then something is wrong with the kickstart file. ESXi Auto-Installer generates the kickstart file based on the data provided to start an installation. Sometimes there is an unforseen configuration issue or typo that causes the kickstart to fail and you need to find out why.
During the installation, when you see the kickstart error, use the following steps to identify the root cause.

 1. Note what section there error is in. It could be in %firstboot or %pre. Also note the line number.
 2. You can view the kickstart file in your ESXi Auto-Installer's Status page.
 3. On the ESXi Console, while the error is displayed on the screen, press ALT+F1 to enter the command line mode.
 4. Login with user name `root` and no password.
 5. `cd /var/log`
 6. `vi weasel.log`
 7. Review the file for clues about what went wrong.

Here is an example of a bad route in the %pre section.
![Kickstart Log](doc_images/kickstartlog.png)


### Using the Static Routes feature causes my installation to fail.
Currently, the static routes feature is not meant for routes related to the management IP address after the ESXi host is installed. It's designed to help with certain storage connectivity issues that can come up during the ESXi installation process.
For now, "standard" IP Static Routing will need to apply those outside of the ESXi Auto-Installer after your installation is complete.

Here is a more in-depth explanation:\
The static routes are applied during the %pre phase of the kickstart process. This is before the Mgmt IP address is assigned. Thus, you cannot use a static route that references a gateway accessible only by the Mgmt IP address.
The static routes are intended for IP interfaces that come up during the server BIOS/POST. For example, a hardware iSCSI adapter will initialize an IP address during POST. The adapter may have its own default gateway specified. However, when the Mgmt IP address is applied, it's default gateway will overwrite any default gateway assigned during the POST phase. This can cause the iSCSI adapter to loose connectivity to the remote storage.
To avoid this scenario, static routes are applied before the Mgmt IP default gateway is applied. This enables the iSCSI adapter to maintain connectivity to storage after the Mgmt IP default gateway gets applied.

### When will you add an option to configure the ESXi feature I need?
The ESXi Auto-Installer is specifically designed to be minimalistic, focusing only on the installation of ESXi and basic connectivity. There are many other tools that can already configure ESXi **once it's online**. You're expected to use a different tool to configure ESXi after ESXi Auto-Installer brings the server online.

> This project is not about replace existing tools, it's about enabling them.

Thus, the ESXi Auto-Installer project will not contain configuration options. The big exception to this rule is enabling the SSH service. This is because a lot of tools require SSH in order to connect to ESXi.

Instead of add features to configuration ESXi, this project will focus on automation feature so it can be used by existing tools.\
That said we do have a few things we hope to bring you in the future that may help. For example, we want you to be able to add scripts that run on first boot. This should provide flexibility if you need a special configuration.
