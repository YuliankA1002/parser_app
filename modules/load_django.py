"""Bootstrap Django so its ORM can be used from scripts outside the project."""

import os
import sys

import django

# Add path to the project
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'braincomua_project')
    )
)

os.environ['DJANGO_SETTINGS_MODULE'] = 'braincomua_project.settings'

django.setup()
