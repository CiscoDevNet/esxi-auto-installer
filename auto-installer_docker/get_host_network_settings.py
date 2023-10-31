from sys import path

path.append("auto-installer_flask")
from config import *
from helper_functions import *


if __name__ == "__main__":
    NETWORK_DATA = get_host_network_settings()
    # return NETWORK_DATA so it can be used by shell script
    print(f"{NETWORK_DATA[0]} {NETWORK_DATA[1]} {NETWORK_DATA[2]} {NETWORK_DATA[3]}")
