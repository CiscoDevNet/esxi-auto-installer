# FROM python:3.10-slim-buster
FROM ubuntu:20.04

WORKDIR /opt/eai/
COPY requirements.txt .
COPY . .
RUN mkdir /opt/eai/ks
RUN mkdir /opt/eai/custom-iso
RUN mkdir -p /opt/eai/upload/mnt
RUN apt update -y
RUN apt install python3-pip genisoimage -y
RUN pip install --no-cache-dir -r requirements.txt
