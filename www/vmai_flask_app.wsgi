#!/usr/bin/python3
import logging
import sys

logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, '/var/www/demo/')
from autoinstaller_gui import app as application
application.secret_key = 'cll-vmware-auto-installer'
