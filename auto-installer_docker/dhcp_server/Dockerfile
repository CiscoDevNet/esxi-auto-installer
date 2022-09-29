# FROM python:3.10-slim-buster
FROM ubuntu:20.04

RUN apt update -y
RUN apt install isc-dhcp-server supervisor -y
RUN touch /var/lib/dhcp/dhcpd.leases
COPY supervisord.conf /etc/supervisor/
COPY run_isc-dhcp-server.sh /opt/

EXPOSE 67
CMD ["/usr/bin/python3", "/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]