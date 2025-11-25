FROM ubuntu:24.04

WORKDIR /opt/eai/
RUN echo "deb [arch=amd64] http://download.proxmox.com/debian/pve bookworm pve-no-subscription" > /etc/apt/sources.list.d/pve-install-repo.list
# COPY proxmox-release-bookworm.gpg /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg
ADD https://enterprise.proxmox.com/debian/proxmox-release-bookworm.gpg /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg
RUN chmod a+r /etc/apt/trusted.gpg.d/proxmox-release-bookworm.gpg
RUN apt update -y
RUN apt install python3-pip genisoimage xorriso proxmox-auto-install-assistant -y 
RUN mkdir /opt/eai/custom-iso
RUN mkdir -p /opt/eai/upload/mnt
RUN mkdir -p /opt/eai/proxmox-iso
RUN mkdir -p /opt/eai/answerfiles
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --break-system-packages
COPY . .