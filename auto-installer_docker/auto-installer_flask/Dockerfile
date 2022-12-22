FROM ubuntu:20.04

WORKDIR /opt/eai/
RUN apt update -y
RUN apt install python3-pip genisoimage -y
RUN mkdir /opt/eai/custom-iso
RUN mkdir -p /opt/eai/upload/mnt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .