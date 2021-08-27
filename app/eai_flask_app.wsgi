#!/usr/bin/python3
import sys
sys.path.insert(0, '/opt/eai/app/')
# TODO: use APPDIR from config.py instead of fixed path + document necessary changes for Apache config

from autoinstaller_gui import app as application
application.secret_key = 'cll-vmware-auto-installer'
