#!/usr/bin/python3
import sys
sys.path.insert(0, '/opt/eai/app/')

from autoinstaller_gui import app as application
application.secret_key = 'cll-vmware-auto-installer'
