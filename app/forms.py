"""Form class declaration."""
from flask_wtf import FlaskForm
from wtforms import (StringField,
                     TextAreaField,
                     SubmitField,
                     PasswordField,
                     DateField,
                     SelectField,
                     TextField)
from wtforms.validators import (DataRequired,
                                Email,
                                EqualTo,
                                Length,
                                URL)

class GatherInput(FlaskForm):
  """Gather input for ESXi deployment."""
  #iso = SelectField('', [DataRequired()],
  #                      choices=[('esxi67u3', 'VMware-ESXi-6.7.0_U3_Installer-14320388_Custom_Cisco_6.7.3.1.iso'),
  #                               ('esxi65u3', 'VMware-ESXi-6.5.0_U3_Installer-13932383_Custom_Cisco_6.5.3.1.iso'),
  #                               ('esxi65u2', 'VMware-ESXi-6.5.0_U2_Installer-9298722-Custom-Cisco-6.5.2.2.iso'),
  #                              ])
