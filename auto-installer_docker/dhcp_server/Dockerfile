FROM ubuntu:20.04

RUN apt update -y
RUN apt install isc-dhcp-server supervisor pxelinux tftpd-hpa -y
RUN touch /var/lib/dhcp/dhcpd.leases
COPY supervisord.conf /etc/supervisor/
COPY run_isc-dhcp-server.sh /opt/
RUN chmod +x /opt/run_isc-dhcp-server.sh
COPY tftpd-hpa /etc/default/tftpd-hpa
RUN mkdir /tftpboot
RUN /etc/init.d/tftpd-hpa start

EXPOSE 67 69
CMD ["/usr/bin/python3", "/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]