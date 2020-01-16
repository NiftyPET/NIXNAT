""" NIXNAT: functions for basic setup and operations needed for communication with XNAT.
"""
__author__    = "Pawel Markiewicz"
__copyright__ = "Copyright 2019"
#-------------------------------------------------------------------------------

import os
import getpass
import json
from stat import *
from . import xnat


def create_dir(pth):
    if not os.path.exists(pth):    
        os.makedirs(pth)


def setup_access(outpath='', fcrdntls='xnat.json'):

    if not os.path.isdir(outpath):
        outpath = os.path.join( os.path.expanduser('~'), '.niftypet')

    create_dir(outpath)

    prj = input('ia> enter below the name of the XNAT project:\n')
    prj = prj.strip()

    url = input('ia> enter below the URL address of the XNAT server:\n')
    url = url.replace('\'', '').strip()

    usr = input('ia> enter below your username:\n')
    pss = getpass.getpass(prompt='ia> enter below your password [optional]:\n')
    usrpsswd = usr+':'+pss

    sbj = url + '/data/projects/' + prj + '/subjects'

    xc = {}
    xc['prj'] = prj
    xc['url'] = url
    xc['usrpwd'] = usrpsswd
    xc['sbj'] = sbj


    #> export the user and server data to a JSON file
    fnm = os.path.join(outpath, fcrdntls)
    with open(fnm, 'w') as fp:
        json.dump(xc, fp)

    #> changes the permission only for the user to be able to write and read
    os.chmod(fnm, S_IWUSR|S_IREAD)

    with open(fnm, 'r') as fp:
        xc = json.load(fp)


def establish_connection(
        path=os.path.join( os.path.expanduser('~'), '.niftypet'),
        fcrdntls = 'xnat.json'
    ):


    with open(os.path.join(path, fcrdntls)) as fj:
        xc = json.load(fj)


    #> establish a single session with a cookie to reuse it
    sessionID = xnat.post_data(xc['url']+'/data/JSESSIONID', '', usrpwd=xc['usrpwd'])
    if 'Error' in  sessionID or 'error' in  sessionID or 'failed' in  sessionID:
        raise ValueError('Login failed!')
    else:
        cookie = 'JSESSIONID='+sessionID
        xc['cookie'] = cookie

    return xc