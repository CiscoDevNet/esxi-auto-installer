# Auxiliary funtions library

import socket


def get_host_ip_address():
    """
    Get host IP address.

    :param n/a
    :return: (str) IP address, eg. 192.168.100.100
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 1))  # connect() for UDP doesn't send packets
    return s.getsockname()[0]