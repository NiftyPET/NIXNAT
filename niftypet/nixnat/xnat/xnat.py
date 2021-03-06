import os
import sys
import csv
import zipfile
import re
from subprocess import call
import glob
import platform

import numpy as np
import math
import pydicom as dcm


#--------------
import pycurl
import json
import io
from io import StringIO
from datetime import datetime
#--------------

#-------------------------------------------------------------------------------
# LOGGING
#-------------------------------------------------------------------------------
import logging

#> console handler
ch = logging.StreamHandler()
formatter = logging.Formatter(
    '\n%(levelname)s> %(asctime)s - %(name)s - %(funcName)s\n> %(message)s'
    )
ch.setFormatter(formatter)
logging.getLogger(__name__).addHandler(ch)

def get_logger(name):
    return logging.getLogger(name)

#> default log level (10-debug, 20-info, ...)
log_default = logging.WARNING
#-------------------------------------------------------------------------------



# DICOM extensions
dcm_ext = ('dcm', 'DCM', 'ima', 'IMA')


# ------------------------------------------------------------------------------
def create_dir(pth):
    if not os.path.exists(pth):    
        os.makedirs(pth)
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
def time_stamp(simple_ascii=False):
    now    = datetime.now()
    if simple_ascii:
        nowstr = str(now.year)+'-'+str(now.month)+'-'+str(now.day)+'_'+str(now.hour)+'h'+str(now.minute)
    else:
        nowstr = str(now.year)+'-'+str(now.month)+'-'+str(now.day)+' '+str(now.hour)+':'+str(now.minute)
    return nowstr
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
def dcminfo(dcmvar, verbose=False, Cnt=None):
    ''' Get basic info about the DICOM file/header.
    '''

    #> check if the dictionary of constant is given
    if Cnt is None:
        Cnt = {}

    #-------------------------------------------
    #> set the logger and its level of verbose
    log = get_logger(__name__)

    if 'LOG' not in Cnt and verbose>=1:
        log.setLevel(logging.INFO)
    elif 'LOG' in Cnt:
        log.setLevel(Cnt['LOG'])
    else:
        log.setLevel(log_default)
    #-------------------------------------------


    if isinstance(dcmvar, str):
        log.info('provided DICOM file:', dcmvar)
        dhdr = dcm.dcmread(dcmvar)
    elif isinstance(dcmvar, dict):
        dhdr = dcmvar
    elif isinstance(dcmvar, dcm.dataset.FileDataset):
        dhdr = dcmvar

    dtype   = dhdr[0x08, 0x08].value
    log.info('Image Type:', dtype)

    #-------------------------------------------
    #> scanner ID
    scanner_vendor = 'unknown'
    if [0x008, 0x070] in dhdr:
        scanner_vendor = dhdr[0x008, 0x070].value

    scanner_model = 'unknown'
    if [0x008, 0x1090] in dhdr:
        scanner_model = dhdr[0x008, 0x1090].value

    scanner_id = 'other'
    if any(s in scanner_model for s in ['mMR', 'Biograph']) and 'siemens' in scanner_vendor.lower():
        scanner_id = 'mmr'
    #-------------------------------------------

    #> CSA type (mMR)
    csatype = ''
    if [0x29, 0x1108] in dhdr:
        csatype = dhdr[0x29, 0x1108].value
        log.info('CSA Data Type:', csatype)

    #> DICOM comment or on MR parameters
    cmmnt   = ''
    if [0x20, 0x4000] in dhdr:
        cmmnt = dhdr[0x0020, 0x4000].value
        log.info('Comments:', cmmnt)

    #> MR parameters (echo time, etc) 
    TR = 0
    TE = 0
    if [0x18, 0x80] in dhdr:
        TR = float(dhdr[0x18, 0x80].value)
        log.info('TR:', TR)
    if [0x18, 0x81] in dhdr:
        TE = float(dhdr[0x18, 0x81].value)
        log.info('TE:', TE)


    #> check if it is norm file
    if any('PET_NORM' in s for s in dtype) or cmmnt=='PET Normalization data' or csatype=='MRPETNORM':
        out = ['raw', 'norm', scanner_id]

    elif any('PET_LISTMODE' in s for s in dtype) or cmmnt=='Listmode' or csatype=='MRPETLM_LARGE':
        out = ['raw', 'list', scanner_id]

    elif any('MRPET_UMAP3D' in s for s in dtype) or cmmnt=='MR based umap':
        out = ['raw', 'mumap', 'ute', 'mr', scanner_id]

    elif TR>400 and TR<2500 and TE<20:
        out = ['mr', 't1', scanner_id]

    elif TR>2500 and TE>50:
        out = ['mr', 't2', scanner_id]

    #> UTE's two sequences: UTE2
    elif TR<50 and TE<20 and TE>1:
        out = ['mr', 'ute', 'ute2', scanner_id]

    #> UTE1
    elif TR<50 and TE<20 and TE<0.1 and TR>0 and TE>0:
        out = ['mr', 'ute', 'ute1', scanner_id]

    #> physio data
    elif 'PET_PHYSIO' in dtype or 'physio' in cmmnt.lower():
        out = ['raw', 'physio', scanner_id]

    else:
        out = ['unknown', str(cmmnt.lower())]

    return out
# ------------------------------------------------------------------------------




#-------------------------------------------------------------------------------
def get_list(xnaturi, cookie='', usrpwd=''):
    buff = io.BytesIO()
    c = pycurl.Curl()
    if cookie:
        c.setopt(pycurl.COOKIE, cookie)
    elif usrpwd:
        c.setopt(c.USERPWD, usrpwd)
    else:
        raise NameError('Session ID or username:password are not given')
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
    c.setopt(c.VERBOSE, 0)
    c.setopt(c.URL, xnaturi )
    c.setopt(c.WRITEDATA, buff)
    c.perform()
    c.close()
    # convert to json dictionary in python
    outjson = json.loads( buff.getvalue() )
    return outjson['ResultSet']['Result']

def get_data(xnaturi, frmt='json', cookie='', usrpwd=''):
    buff = io.BytesIO()
    c = pycurl.Curl()
    if cookie:
        c.setopt(pycurl.COOKIE, cookie)
    if usrpwd:
        c.setopt(c.USERPWD, usrpwd)
    else:
        raise NameError('Session ID or username:password are not given')
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
    c.setopt(c.VERBOSE, 0)
    c.setopt(c.URL, xnaturi )
    c.setopt(c.WRITEDATA, buff)
    c.perform()
    c.close()
    # convert to json dictionary in python
    if frmt=='':
        output = buff.getvalue()
    elif frmt=='json':
        output = json.loads( buff.getvalue() )
    return output

def get_file(xnaturi, fname, cookie='', usrpwd='', Cnt=None):

    #> check if the dictionary of constant is given
    if Cnt is None:
        Cnt = {}

    #-------------------------------------------
    #> set the logger and its level of verbose
    log = get_logger(__name__)
    log.setLevel(Cnt.get('LOG', log_default))
    #-------------------------------------------

    try:
        fn = open(fname, 'wb')
        c = pycurl.Curl()
        if cookie:
            c.setopt(pycurl.COOKIE, cookie)
        else:
            c.setopt(c.USERPWD, usrpwd)
        c.setopt(pycurl.SSL_VERIFYPEER, 0)
        c.setopt(pycurl.SSL_VERIFYHOST, 0)
        c.setopt(c.VERBOSE, 0)
        c.setopt(c.URL, xnaturi )
        c.setopt(c.WRITEDATA, fn)
        c.setopt(pycurl.FOLLOWLOCATION, 0)
        c.setopt(pycurl.NOPROGRESS, 0)
        c.perform()
        c.close()
        fn.close()
    except pycurl.error as pe:
        a = f'''
        ==============================================================
        e> pycurl error: {pe}
        ==============================================================

        w> no data.

        '''
        log.error(a)
        return -1

    else:
        a = f'''
        \rpycurl download done.
        \r---------------------
        '''
        log.info(a)
    return 0
#----------------------------------------------------------------------------------------------------------


#----------------------------------------------------------------------------------------------------------
def put_data(xnaturi, cookie='', usrpwd=''):
    """e.g., create a container"""
    c = pycurl.Curl()
    if cookie:
        c.setopt(pycurl.COOKIE, cookie)
    elif usrpwd:
        c.setopt(c.USERPWD, usrpwd)
    else:
        raise NameError('Session ID or username:password are not given')
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
    c.setopt(c.VERBOSE, 0)
    c.setopt(c.URL, xnaturi )
    c.setopt(c.CUSTOMREQUEST, 'PUT')
    c.perform()
    c.close()

def del_data(xnaturi, cookie='', usrpwd=''):
    """e.g., create a container"""
    c = pycurl.Curl()
    if cookie:
        c.setopt(pycurl.COOKIE, cookie)
    elif usrpwd:
        c.setopt(c.USERPWD, usrpwd)
    else:
        raise NameError('Session ID or username:password are not given')
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
    c.setopt(c.VERBOSE, 0)
    c.setopt(c.URL, xnaturi )
    c.setopt(c.CUSTOMREQUEST, 'DELETE')
    c.perform()
    c.close()

def post_data(xnaturi, post_data, verbose=0, PUT=False,  cookie='', usrpwd=''):
    buff = io.BytesIO()
    c = pycurl.Curl()
    if cookie:
        c.setopt(pycurl.COOKIE, cookie)
    elif usrpwd:
        c.setopt(c.USERPWD, usrpwd)
    else:
        raise NameError('Session ID or username:password are not given')
    c.setopt(c.USERPWD, usrpwd)
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
    c.setopt(c.VERBOSE, verbose)
    c.setopt(c.URL, xnaturi )
    if PUT: c.setopt(c.CUSTOMREQUEST, 'PUT')
    c.setopt(c.POSTFIELDS, post_data)
    c.setopt(c.WRITEFUNCTION, buff.write)
    c.perform()
    c.close()
    return buff.getvalue().decode('UTF-8')

def put_file(xnaturi, filepath, cookie='', usrpwd=''):
    """upload file to xnat server"""
    c = pycurl.Curl()
    if cookie:
        c.setopt(pycurl.COOKIE, cookie)
    elif usrpwd:
        c.setopt(c.USERPWD, usrpwd)
    else:
        raise NameError('Session ID or username:password are not given')
    c.setopt(pycurl.SSL_VERIFYPEER, 0)
    c.setopt(pycurl.SSL_VERIFYHOST, 0)
    c.setopt(pycurl.NOPROGRESS, 0)
    c.setopt(c.VERBOSE, 0)
    c.setopt(c.URL, xnaturi )
    c.setopt(c.HTTPPOST, [('fileupload', (c.FORM_FILE, filepath,)),])
    c.perform()
    c.close()
#----------------------------------------------------------------------------------------------------------



#----------------------------------------------------------------------------------------------------------
def put_PetMrRes(usrpwd, xnatsbj, sbjix, lbl, frmt, fpth):
    # get the experiment id
    expt = get_xnatList(usrpwd, xnatsbj+'/' +sbjix+ '/experiments?xsiType=xnat:petmrSessionData&format=json&columns=ID')
    # prepare the uri
    xnaturi = xnatsbj+'/' +sbjix+ '/experiments/' + expt[0]['ID'] + '/resources/' +lbl+ '?xsi:type=xnat:resourceCatalog&format='+frmt
    xnat_put(usrpwd, xnaturi)
    # upload
    xnaturi = xnatsbj+'/' +sbjix+ '/experiments/' + expt[0]['ID'] + '/resources/' +lbl+ '/files'
    xnat_upload(usrpwd, xnaturi, fpth)
#----------------------------------------------------------------------------------------------------------



#===============================================================================
#> GET SCANS from XNAT
#===============================================================================

def getscan(
        sbjix,
        expt,
        xc,
        cookie = '',
        scan_types = [],
        scan_ids = [],
        dformat = ['DICOM', 'NIFTI'],
        outpath = '',
        fcomment = '',
        Cnt=None,
        info_only=False,
        output_quality=True,
        #close_session=True,
        ):

    '''
        expt:  XNAT experiment as a dictionary or string (ID or label)
    '''

    #> check if the dictionary of constant is given
    if Cnt is None:
        Cnt = {}

    #-------------------------------------------
    #> set the logger and its level of verbose
    log = get_logger(__name__)
    log.setLevel(Cnt.get('LOG', log_default))
    #-------------------------------------------


    if not cookie and 'cookie' not in xc:
        sessionID = post_data(xc['url']+'/data/JSESSIONID', '', usrpwd=xc['usrpwd'])
        cookie = 'JSESSIONID='+sessionID
        log.warning('using a new session/cookie for this XNAT connection.')
    elif not cookie and 'cookie' in xc:
        cookie = xc['cookie']

    #>------------------------------------------
    #> input for experiment
    if isinstance(expt, str):
        expid = expt
    elif isinstance(expt, dict):
        expid = expt['ID']
    #>------------------------------------------


    #>------------------------------------------
    #> input for scan
    if isinstance(scan_types, str):
        scan_types = [scan_types]

    if isinstance(scan_ids, str):
        scan_ids = [scan_ids]

    if isinstance(dformat, str):
        dformat = [dformat]
    #>------------------------------------------


    #> output dictionary
    out = {}
    out['cookie'] = cookie

    if outpath=='':
        if 'opth' in xc and os.path.isdir(xc['opth']):
            opth = xc['opth']
        else:
            if platform.system() in ['Linux', 'Darwin']:
                opth = os.path.join(os.path.expanduser('~'), 'XNATscans')
            elif platform.system() == 'Windows' :
                opth = os.path.join(os.getenv('LOCALAPPDATA'), 'XNATscans')
            else:
                raise IOError('e> unknown system and no output folder provided!')
    else:
        opth = outpath

    log.info('using this output path: {}.'.format(opth))

    scans = get_list(
        xc['sbj']+'/' +sbjix+ '/experiments/' + expid + '/scans',
        cookie=cookie
    )

    all_scan_types = [(s['type'],s['quality'],s['ID']) for s in scans]

    # import pdb; pdb.set_trace()

    picked_scans = []
    if scan_types!=[]:
        for st in scan_types:
            picked_scans.extend([s for s in all_scan_types if st in s[0]])
    
    elif scan_ids!=[]:
        for si in scan_ids:
            picked_scans.extend([s for s in all_scan_types if si == s[2]])

    else:
        log.info('using all scans')
        picked_scans = all_scan_types


    for scn in picked_scans:

        stype   = str(scn[0])
        quality = str(scn[1])
        sid     = str(scn[2])

        s_type_id = sid+'_'+stype

        log.info('''SCAN:
                \r   scant type: {}
                \r   quality: {}
                \r   ID: {}'''.format(stype, quality, sid))

        entries = get_list(
            xc['sbj']+'/' +sbjix+ '/experiments/' + expid + '/scans/'+sid+'/resources',
            cookie=cookie
        )

        for e in entries:

            if e['format'] in dformat:

                out[s_type_id] = []

                files = get_list(
                        xc['sbj']+'/' +sbjix+ '/experiments/' + expid \
                            + '/scans/'+sid+'/resources/'+ e['format']+ '/files',
                        cookie=cookie
                        )

                #> scan path
                if output_quality:
                    spth = os.path.join( opth,  s_type_id+'_q-'+quality)
                else:
                    spth = os.path.join( opth,  s_type_id)
                create_dir(spth)

                
                if info_only:
                    out[s_type_id] = files

                #> download all files in every scan as requested
                else:
                    for i in range(len(files)):
                        
                        if output_quality:
                            fname = 'scan-'+s_type_id+'_q-'+quality+fcomment\
                                +'.'+files[i]['Name'].split('.',1)[-1]
                        else:
                            fname = 'scan-'+s_type_id+fcomment\
                                +'.'+files[i]['Name'].split('.',1)[-1]

                        status = get_file(
                            xc['url']+files[i]['URI'],
                            os.path.join(spth, fname),
                            cookie=cookie,
                            Cnt=Cnt)

                        if status<0:
                            log.error('no scan data for {}'.format(scntype))
                        else:
                            out[s_type_id].append(os.path.join(spth, fname))
                    
                    if len(files)<1: 
                        log.error('no scan data for {}'.format(scntype))

    log.info('file information is contained in the output dictionary.')
    return out
#===============================================================================




#===============================================================================
#> GET RESOURCES (RAW FILES, PROCESSED IMAGES) from XNAT
#===============================================================================

def getresources(
        rfiles,
        xc,
        outpath = '',
        cookie = '',
        ):


    if not cookie:
        sessionID = post_data(xc['url']+'/data/JSESSIONID', '', usrpwd=xc['usrpwd'])
        cookie = 'JSESSIONID='+sessionID

    #> output dictionary
    out = {}
    out['cookie'] = cookie

    if outpath=='':
        if os.path.isdir(xc['opth']):
            opth = xc['opth']
        else:
            if platform.system() in ['Linux', 'Darwin']:
                opth = os.path.join(os.path.expanduser('~'), 'xnat_scans')
            elif platform.system() == 'Windows' :
                opth = os.path.join(os.getenv('LOCALAPPDATA'), 'xnat_scans')
            else:
                raise IOError('e> unknown system and no output folder provided!')
    else:
        opth = outpath


    for i in range(len(rfiles)):

        #> check if the file is already downloaded:
        if  os.path.isfile ( os.path.join(opth, rfiles[i]['Name']) ) and \
            str(os.path.getsize(os.path.join(opth, rfiles[i]['Name'])))==rfiles[i]['Size']:
            
            print('i> file of the same size,',rfiles[i]['Name'], 'already exists: skipping download.')
            
            if '.dcm' in rfiles[i]['Name'].lower():
                if 'dcm' not in out: out['dcm'] = []
                out['dcm'].append(os.path.join(opth, rfiles[i]['Name']))
            elif '.bf' in rfiles[i]['Name'].lower():
                if 'bf' not in out: out['bf'] = []
                out['bf'].append(os.path.join(opth, rfiles[i]['Name']))
            elif '.ima' in rfiles[i]['Name'].lower():
                if 'ima' not in out: out['ima'] = []
                out['ima'].append(os.path.join(opth, rfiles[i]['Name']))
            elif '.nii' in rfiles[i]['Name'].lower():
                if 'nii' not in out: out['ima'] = []
                out['nii'].append(os.path.join(opth, rfiles[i]['Name']))

        
        else:
            status = get_file(
                xc['url']+rfiles[i]['URI'], os.path.join(opth, rfiles[i]['Name']),
                cookie = cookie
            )
            if status<0:
                print('e> error downloading:', fcomment)
            else:
                if '.dcm' in rfiles[i]['Name'].lower():
                    if 'dcm' not in out: out['dcm'] = []
                    out['dcm'].append(os.path.join(opth, rfiles[i]['Name']))
                    
                elif '.bf' in rfiles[i]['Name'].lower():
                    if 'bf' not in out: out['bf'] = []
                    out['bf'].append(os.path.join(opth, rfiles[i]['Name']))
                    
                elif '.ima' in rfiles[i]['Name'].lower():
                    if 'ima' not in out: out['ima'] = []
                    out['ima'].append(os.path.join(opth, rfiles[i]['Name']))
                elif '.nii' in rfiles[i]['Name'].lower():
                    if 'nii' not in out: out['nii'] = []
                    out['nii'].append(os.path.join(opth, rfiles[i]['Name']))
                
    if len(rfiles)<1:
        print('e> requested resources data is missing.')


    return out
