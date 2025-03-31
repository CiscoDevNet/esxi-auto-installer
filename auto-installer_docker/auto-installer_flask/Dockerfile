FROM ubuntu:20.04

WORKDIR /opt/eai/
RUN apt update -y
RUN apt install python3-pip genisoimage -y
RUN mkdir /opt/eai/custom-iso
RUN mkdir -p /opt/eai/upload/mnt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# M7 patch
COPY imcsdk_0.9.16_patch/boot.py /usr/local/lib/python3.8/dist-packages/imcsdk/apis/server/boot.py
COPY imcsdk_0.9.16_patch/vmedia.py /usr/local/lib/python3.8/dist-packages/imcsdk/apis/server/vmedia.py
COPY imcsdk_0.9.16_patch/imchandle.py /usr/local/lib/python3.8/dist-packages/imcsdk/imchandle.py
