#!/usr/bin/env python
"""initialise the NIXNAT package (part of NiftyPET package)"""
__author__      = "Pawel Markiewicz"
__copyright__   = "Copyright 2019 Pawel Markiewicz @ University College London"
#------------------------------------------------------------------------------


from .xnat import xnat

from .xnat.iofun import setup_access
from .xnat.iofun import establish_connection


from .xnat.xnat import get_list
from .xnat.xnat import put_data
from .xnat.xnat import put_file

from .xnat.xnat import post_data
from .xnat.xnat import dcminfo