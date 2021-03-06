"""
Obit pipeline utilities. These functions are generic utlities that may be
useful for any pipeline.
"""

import urllib, urllib2, os.path, pickle, time, sys, socket, signal
import glob, xml.dom.minidom, re, pprint
import ObitTask, Image, AIPSDir, OErr, FArray, VLBACal, FITS, UV, UVDesc, Table
import mjd

def setname (inn, out):
    """ 
Copy file definition from *inn* to *out* as in. Supports both FITS and AIPS files.  
Copies data type, file name, disk, class, etc.

inn  = Obit data object, created with getname, getFITS
out  = ObitTask object
    """
    ################################################################
    # AIPS or Obit?
    if out.__class__ == ObitTask.ObitTask:
        out.DataType = inn.FileType
        out.inDisk   = int(inn.Disk)
        if inn.FileType == 'FITS':
            out.inFile = inn.Fname
        else:   # AIPS
            out.inName  = inn.Aname
            out.inClass = inn.Aclass
            out.inSeq   = int(inn.Aseq)
    else:  # AIPS
        out.inname  = inn.Aname
        out.inclass = inn.Aclass
        out.inseq   = inn.Aseq
        out.indisk  = inn.Disk
    # end setname
    
def setoname (inn, out):
    """ 
Copy file definition from *inn* to *out* as out. Supports both FITS and AIPS
Copies data type, file name, disk, class, etc.

inn  = Obit data object, created with getname, getFITS
out  = ObitTask object
    """
    ################################################################
    # AIPS or Obit?
    if out.__class__ == ObitTask.ObitTask:
        out.DataType = inn.FileType
        out.outDisk   = int(inn.Disk)
        if inn.FileType == 'FITS':
            out.outFile = inn.Fname
        else:   # AIPS
            out.outName  = inn.Aname
            out.outClass = inn.Aclass
            out.outSeq   = int(inn.Aseq)
    else:  # AIPS
        out.outname  = inn.Aname
        out.outclass = inn.Aclass
        out.outseq   = inn.Aseq
        out.outdisk  = inn.Disk
    # end setoname
    
def set2name (in2, out):
    """
Copy file definition from *in2* to *out* as in2. Supports both FITS and AIPS
Copies data type, file name, disk, class, etc.

in2  = Obit data object, created with getname, getFITS
out  = ObitTask object
    """
    ################################################################
    # AIPS or Obit?
    if out.__class__ == ObitTask:
        out.DataType  = in2.FileType
        out.in2Disk   = int(in2.Disk)
        if in2.FileType == 'FITS':
            out.in2File = in2.Fname
        else:   # AIPS
            out.in2Name  = in2.Aname
            out.in2Class = in2.Aclass
            out.in2Seq   = int(in2.Aseq)
    else: # AIPS
        out.in2Name  = in2.Aname
        out.in2Class = in2.Aclass
        out.in2Seq   = in2.Aseq
        out.in2Disk  = in2.Disk
    # end set2name
   
def imstat (inImage, err, blc=[1,1,1,1,1], trc=[0,0,0,0,0], logfile=None):
    """ 
    Get statistics in a specified region of an image plane
    
    Returns dictionary with statistics of selected region with entries:
        - Mean    = Mean value
        - RMSHist = RMS value from a histogram analysis
        - RMS     = Simple RMS value
        - Max     = maximum value
        - MaxPos  = pixel of maximum value
        - Min     = minimum value
        - MinPos  = pixel of minimum value
        - Flux    = Flux density if CLEAN beam given, else -1
        - BeamArea= CLEAN Beam area in pixels
    
    * inImage  = Python Image object, created with getname, getFITS
    * err      = Obit error/message stack
    * blc      = bottom left corner pixel (1-rel)
    * trc      = top right corner pixel (1-rel)
    * logfile  = file to write results to, if None don't print
    """
    ################################################################
    # Read plane
    p    = Image.PReadPlane(inImage,err,blc=blc,trc=trc)
    OErr.printErrMsg(err, "Error with input image")
    head = inImage.Desc.Dict  # Header

    # Get statistics
    Mean = p.Mean
    RMS  = p.RMS
    RawRMS  = p.RawRMS
    MaxPos=[0,0]
    Max = FArray.PMax(p, MaxPos)
    MaxPos[0] = MaxPos[0]+blc[0]
    MaxPos[1] = MaxPos[1]+blc[1]
    MinPos=[0,0]
    Min = FArray.PMin(p, MinPos)
    MinPos[0] = MinPos[0]+blc[0]
    MinPos[1] = MinPos[1]+blc[1]
    # Integrated flux density
    Flux = -1.0
    beamarea = 1.0
    if (head["beamMaj"]>0.0) :
        beamarea = 1.1331*(head["beamMaj"]/abs(head["cdelt"][0])) * \
                   (head["beamMin"]/abs(head["cdelt"][1]))
        Flux = p.Sum/beamarea
    if logfile:
        mess =  "Image statistics:  Region Mean %g, RMSHist %g RMS %g" % (Mean, RMS, RawRMS)
        printMess(mess, logfile)
        mess =  "  Max %g @ pixel %s" % (Max, str(MaxPos))
        printMess(mess, logfile)
        mess = "  Min %g @ pixel %s" % (Min,  str(MinPos))
        printMess(mess, logfile)
        if (head["beamMaj"]>0.0) :
            mess = "  Integrated Flux density %g, beam area = %7.1f pixels" % (Flux, beamarea)
            printMess(mess, logfile)
   
    # Reset BLC, TRC
    blc = [1,1,1,1,1]
    trc = [0,0,0,0,0]
    Image.POpen(inImage, Image.READONLY, err, blc=blc, trc=trc)
    Image.PClose (inImage, err)
    OErr.printErrMsg(err, "Error with input image")
    
    del p, blc, trc
    return {"Mean":Mean,"RMSHist":RMS,"RMS":RawRMS,"Max":Max, \
            "MaxPos":MaxPos,"Min":Min,"MinPos":MinPos,"Flux":Flux,
            "BeamArea":beamarea}
    # end imstat
   
def setupSourceList( slist, uv, err, logfile, check=False, debug=False ):
    """
    Force source list, *slist*, to be a non-empty list.

    If *slist* == None or [], set it to all sources in data set. If *slist* 
    is a string, make it a one-element list.

    * slist = input source name(s)
    * uv = Obit uv data object
    * err = OErr object
    * logfile = pipeline log file
    * check = check mode
    * debug = debug mode
    """
    if slist == None or slist == []:
        slist = VLBACal.VLBAAllSource(uv,err,logfile=logfile,check=check,debug=debug)
    elif type(slist) == str:
        slist = [ slist ]
    return slist

def unique (inn):
    """ 
    Removes duplicate entries from an array of strings.  Returns an array of
    strings, also removes null and blank strings as well as leading or trailing
    blanks.
    
    * inn  = list of strings with possible redundancies
    """
    # Make local working copy and blank redundant entries
    linn = []
    for item in inn:
        sitem = item.strip()
        if len(sitem)>0:
            linn.append(sitem)
    # Remove duplicates from the end of the list
    n = len(linn)
    for jj in range(0,n):
        j = n-jj-1
        for i in range (0,j):
            if (linn[j]==linn[i]):
                linn[j] = ""
                break;
    # end loops
    # Copy to output string
    outl = []
    for item in linn:
        if len(item)>0:
            outl.append(item)
    return outl
# end unique

def AllDest (err, disk=None, Atype="  ", Aname="            ", Aclass="      ",
    Aseq=0):
    """ 
    Delete AIPS files matching a pattern. Strings use AIPS wild cards:
    
         * blank => any
         * '?'   => one of any character
         * "*"   => arbitrary string
         
    * disk      = AIPS disk number, 0=>all
    * Atype     = AIPS entry type, 'MA' or 'UV'; '  => all
    * Aname     = desired AIPS name, using AIPS wildcards, None -> don't check
    * Aclass    = desired AIPS class, using AIPS wildcards, None -> don't check
    * Aseq      = desired AIPS sequence, 0=> any
    """
    ################################################################
    if err.isErr:   # Ignore if error condition
        return
    global Adisk
    if disk==None:
        disk = Adisk
    else:
        if disk>0:
            Adisk = disk
    # NO Confirm
    #prompt = "Do you really want to delete all AIPS "+Atype+" files on disk(s) "\
    #         +str(disk)+"\nwith names matching "+Aname+"."+Aclass+"."+str(Aseq)+ \
    #         " y/n "
    #ans = raw_input(prompt)
    #if ans.startswith('y'):
    AIPSDir.PAllDest (disk, err, Atype=Atype, Aname=Aname, Aclass=Aclass,
                      Aseq=Aseq)
    #else:
    #    print "Not confirmed"
    OErr.printErrMsg(err, "Error with destroying AIPS enreies")
    # end AllDest

def printMess (message, logfile=''):
    """ 
Print message, optionally in logfile
        
* message = message to print
* logfile = logfile for message
    """
    print message
    if logfile and len(logfile) > 0:
        f = file(logfile,'a')
        f.writelines(message+"\n")
        f.close()
    # end printMess

def dhms2day(st):
    """ 
Convert a time string in d/hh:mm:ss.s to days.  Returns time in days.

* st = time string as "d/hh:mm:ss.s"
    """
    ################################################################
    stt = st
    if st.__contains__("/"):
        pp=stt.split("/")
        day = int(pp[0])
        stt = pp[1]
    else:
        day = 0
    pp=stt.split(":")
    if len(pp)>0:
        hour = int(pp[0])
    else:
        hour = 0
    if len(pp)>1:
        min = int(pp[1])
    else:
        min = 0
    if len(pp)>2:
        ssec = float(pp[2])
    else:
        ssec = 0.0
    tim = day + hour/24.0 + min/1440.0 + ssec/86400.0
    return tim
    # end dhms2day

def day2dhms(tim):
    """ 
Convert a time in days to a string as d/hh:mm:ss.s.

* Returns time as string:  "d/hh:mm:ss.s"
* tim       time in days
    """
    ################################################################
    day=int(tim)
    ttim = 24.0*(tim - day)
    thour = min (int(ttim), 23)
    ttim = 60.0*(ttim - thour)
    tmin = min (int(ttim), 59)
    ssec = 60.0*(ttim - tmin)
    tmp = int(ssec*100 + 0.5)  # truncate
    ssec = tmp*0.01
    return str(day)+"/"+str(thour).zfill(2)+":"+str(tmin).zfill(2)+\
           ":"+str(ssec)
    # end day2dhms

def SaveObject (pyobj, file, update):
    """ 
    Save python object to a pickle file
    
    * pyobj    = python object to save
    * file     = pickle file name
    * update   = If True overwrite, otherwise only if file doesn't already exist
    """
    ################################################################
    # Does file exist?, only do this if not or update
    if update or not os.path.isfile(file):
        fd = open(file, "w")
        pickle.dump(pyobj, fd)
        fd.close()
    # end SaveObject
   
def FetchObject (file):
    """ 
    Fetch python object from a pickle file.
    
    * returns python object
    * file     = pickle file name
    """
    ################################################################
    # does it exist?
    if not os.path.lexists(file):
        print "Pickle jar",file,"does not exist"
        return None
    # unpickle file
    fd = open(file, "r")
    pyobj = pickle.load(fd)
    fd.close()
    return pyobj
    # end FetchObject
   
def QueryArchive(startTime, endTime, project=None, format='ALL'):
    """
    Query the NRAO Archive for data files. Return the response as a list of 
    lines.
    
    * startTime = Start of query time range ( YYYY-mmm-DD [ HH:MM:SS ] )
    * endTime = End of query time range
    * project = Project code
    * format = Archive file format. 'Calibrated Data' => FITS AIPS; 
      'Raw Data' => FITS IDI
    """
    freqRange = '1000 - 16000' # frequency range (MHz) (L to U bands)
    # HTTP POST parameters
    dataList = [ ('PROTOCOL','TEXT-stream'),
                 ('TELESCOPE','VLBA'),
                 ('QUERYTYPE','ARCHIVE'),
                 ('OBSFREQ1', freqRange ),
                 ('DATATYPE', format),
                 ('TIMERANGE1', startTime),
                 ('TIMERANGE2', endTime) ]
    if project:
        dataList.append( ('PROJECT_CODE', project) )
    data = urllib.urlencode( dataList )
    url = 'https://archive.nrao.edu/archive/ArchiveQuery'
    # Archive is known to occasionally send a null response. This is an error.
    # At the least, a header line should be returned. Repeat the query 
    # until a non-null response is obtained. If the response contains a header
    # only, repeat the query once to verify.
    lineCount = 0
    while 1:
        response = urllib2.urlopen( url, data ) # Submit query
        lines = response.readlines() # Extract response into a list of lines
        if len(lines) == 0: # null response
            print "Archive response is null. Repeating query."
            lineCount = len(lines)
        else: 
            lines.pop() # remove tailing blank line
        if len(lines) == 1: # Header only, no data
            if lineCount != 1:
                print "Archive response contains no files. " + \
                    "Repeating query to verify."
                lineCount = len(lines)
            else:
                print "Verified: Archive response contains no files."
                break
        elif len(lines) > 1: # Data is present
            break
    return lines

def ParseArchiveResponse( responseLines ):
    """
    Parse the archive response returned by QueryArchive and return a list
    containing one dictionary for each file. The values in each dictionary will
    correspond to items in each row of the query response.  The keys will
    correspond to the items in the response header row, with additional column
    headers added where needed. Redundant columns are not included in the
    dictionaries.
    
    * responseLines = Archive query response returned by QueryArchive
    """
    head = responseLines[0] # header line
    headers = head.split(' ')
    headers.pop(0) # remove leading '#'
    headers.pop(1) # remove extra space
    # Add headers to columns where there are none
    headers[14:] = ['DATE', 'RESPONSE_ROW', '?', 'FILESIZE_UNIT']
    fileList = []
    for line in responseLines[1:]:
        metadata = line.split(',')
        # Remove redundant metadata
        metadata[14:19] = [] 
        metadata.pop(17)
        dict = {}
        for i,d in enumerate(metadata): # iterate over every column
            dict[ headers[i] ] = d.strip()
        # remove duplicateslogical_file
        if (len(fileList)==0) or \
               (dict["logical_file"]!=fileList[len(fileList)-1]["logical_file"]):
            # print "DEBUG dict",dict
            fileList.append( dict )
    return fileList

def FilterFileList( fileList, logFile=None, ignoreIDI = False, showAllIDI = False ):
    """
    Filter the archive response file list.

    Remove data sets that are not of interest from *fileList*. Return a list of
    removed data sets. By default, FITS-IDI files for observations that end on
    or before 2009-Dec-10 are removed.  However, parameters *ignoreIDI* and
    *showAllIDI* can be used to ignore or show all IDI files for all dates.
    *showAllIDI* takes precendence over *ignoreIDI*.  (2009-Dec-10 is the last
    day of observations processed with the old-correlator.) 

    * fileList = list of dictionaries returned by ParseArchiveResponse
    * logFile  = where to write messages
    * ignoreIDI = remove files with format FITS-IDI
    * showAllIDI = don't remove any IDI files regardless of observing date
    """
    # Remove files with old filename formats. For BL0137 there are old files
    # and new files; John says the filename format differs but the data
    # is the same.
    pattern = re.compile(r"/home/archive_VLBA[0-9]+/projects/VLBA")
    filteredList = []
    filteredTemp = []
    fileList_copy = fileList[:]
    for fileDict in fileList_copy:
        matchObj = re.match( pattern, fileDict['file_root'] )
        if matchObj:
            filteredTemp.append( fileDict )
            fileList.remove( fileDict )
    if len(filteredTemp) > 0:
        mess = "INFO "+str(len(filteredTemp)) +  \
        " old-style-filename data sets filtered from list." + \
        " (" + str(len(fileList)) + " remain)"
        printMess(mess, logFile)
        filteredList += filteredTemp

    # Remove files with format 'VLBAset' (they appear to be duplicates)
    filteredTemp = []
    fileList_copy = fileList[:]
    for fileDict in fileList_copy:
        if fileDict['format'] == 'VLBAset':
            filteredTemp.append( fileDict )
            fileList.remove( fileDict )
    if len(filteredTemp) > 0:
        mess = "INFO "+str(len(filteredTemp)) +  \
            " files with format='VLBAset' filtered from list." + \
            " (" + str(len(fileList)) + " remain)"
        printMess(mess, logFile)
        filteredList += filteredTemp

    # Remove files with format 'FITS-IDI' *if* showAllIDI==False and either
    # ignoreIDI==True or file was observed before 2009 Dec 11.
    filteredTemp = []
    fileList_copy = fileList[:]
    if not showAllIDI:
        fileList_copy = fileList[:]
        for fileDict in fileList_copy:
            if fileDict['format'] == 'FITS-IDI' and \
               ( ignoreIDI or
                 ( dateStringToMJD(fileDict['stoptime']) <
                   dateStringToMJD('09-Dec-11 00:00:00') 
                 )
               ):
                filteredTemp.append( fileDict )
                fileList.remove( fileDict )
        if len(filteredTemp):
            mess = "INFO "+str(len(filteredTemp)) +  \
                " files with format='FITS-IDI' filtered from list." + \
                " (" + str(len(fileList)) + " remain)"
            printMess(mess, logFile)
            filteredList += filteredTemp
    return filteredList

def DownloadArchiveFile( fileDict, destination, safe=True, logFile=None ):
    """
    Download a file from the archive. Return the output of urllib2.urlopen.  If
    *safe* = True and the file already exists in the download area, ask the
    user what to do.  If the user aborts the download, return None.
    
    * fileDict = archive file dictionary from ParseArchiveResponse
    * destination = path to destination directory
    * safe = if True, ask user before overwriting local files
    """
    url = "https://archive.nrao.edu/archive/ArchiveDeliver"
    filename = fileDict['logical_file']
    string = fileDict['telescope:config']
    telescope = string[ 0 : string.find(':') ] # extract telescope name
    dataList = [ ('FILE_ID', filename ),
                 ('telescope', telescope ),
                 ('deliver_dir', destination) ]
    fullDLPath = destination + '/' + filename
    if os.path.exists( fullDLPath ):
        if safe:
            print( "File " + fullDLPath + " already exists in download area." )
            overwrite = nonBlockingRawInput( 
                '  Overwrite? {60 sec to respond} (y/n) [y]: ', timeout=60, logFile=logFile)
            if ( overwrite and overwrite[0].lower() == 'n' ):
                print "Using file already in download area."
                return None
            else:
                os.remove( fullDLPath )
        else:
            os.remove( fullDLPath )
    data = urllib.urlencode( dataList )
    mess = "DEBUG Submitting download request with parameters:\n" + \
                 "  url = " + url + "\n" + "  data = " + data
    printMess(mess, logFile)
    response = urllib2.urlopen( url, data )
    return response

def DownloadIDIFiles( fileDict, destination, logFile=None ):
    """
    Download a set of FITS IDI files corresponding to a UVFITS file.  If all
    the files already exist in the download area, ask the user what to do.  To
    avoid overwhelming the archive, poll the download status after requesting
    each IDI file. Return a list of IDI file dictionaries.
    
    * fileDict = archive file dictionary from ParseArchiveResponse
    * destination = path to destination directory
    """
    # Get start/stop times with 4-digit year format
    starttime = fileDict['starttime']
    stoptime = fileDict['stoptime']
    yr = []
    yr.append( int( starttime[0:2] ) )
    yr.append( int(  stoptime[0:2] ) )
    for i,y in enumerate(yr):
        if   y <  80: y += 2000
        elif y >= 80: y += 1900
        yr[i] = str(y)
    starttime = yr[0] + starttime[2:]
    stoptime = yr[1] + stoptime[2:]
    # Query for IDI files
    mess = "DEBUG Sending query..."
    printMess(mess, logFile)
    response = QueryArchive( starttime, stoptime, format='Raw Data' )
    IDIList = ParseArchiveResponse( response )
    print "IDI Files: \n" + SummarizeArchiveResponse( IDIList )
    fileExists = []
    overwrite = False
    for file in IDIList:
        fullDLPath = destination + '/' + file['logical_file']
        if os.path.exists( fullDLPath ):
            fileExists.append( fullDLPath )
    if fileExists and len(fileExists) == len(IDIList):
        mess = "INFO All IDI files already exist in download area:\n" + \
            pprint.pformat(fullDLPath) 
        printMess(mess, logFile)
        overwrite = nonBlockingRawInput( 
            '  Overwrite? {60 sec to respond} (y/n) [y]: ', timeout=60 )
        if ( overwrite and overwrite[0].lower() == 'n' ):
            overwrite = True
            print "Using files already in download area."
    if not overwrite:
        for file in IDIList:
            fullDLPath = destination + '/' + file['logical_file']
            DownloadArchiveFile( file, destination, safe=False )
            PollDownloadStatus( file, destination )
    return IDIList
   
def PollDownloadStatus( fileDict, destination, sleepTotal = 30 * 60, logFile=None ):
    """
    Poll the status of a file download from the archive. 
    
    Return only when download is complete. Re-submit download request if archive
    does not respond after *sleepTotal* seconds.
    
    * filepath = full path to file
    * destination = path to FITS directory
    """
    filename = fileDict['logical_file']
    finishName = destination + '/' + filename
    downloadName = finishName + '.loading'
    waitFlag = False
    inProgressFlag = False
    mess = "DEBUG Checking download status. Looking for 1 of 2 files:\n" + \
        finishName + "\n" + downloadName
    printMess(mess, logFile)
    sleepIncrement = 3 # seconds
    sleepTime = 0
    while 1: # infinite loop
        if not os.path.exists( downloadName ) and not os.path.exists( finishName ):
            if not waitFlag:
                mess = "INFO Waiting for download to initiate. (" + \
                    time.strftime('%Y-%m-%d %X %Z') + ")" 
                printMess(mess, logFile)
                waitFlag = True
            time.sleep( sleepIncrement )
            sleepTime += sleepIncrement
        elif os.path.exists( downloadName ):
            if not inProgressFlag:
                mess = "INFO Download in progress... (" + \
                    time.strftime('%Y-%m-%d %X %Z') + ")" 
                printMess(mess, logFile)
                inProgressFlag = True
            time.sleep( sleepIncrement )
            sleepTime += sleepIncrement
        elif os.path.exists( finishName ):
            mess = "INFO Download complete."
            printMess(mess, logFile)
            return
        # Submit new download request after waiting *sleepTime* seconds.
        # (because the archive sometimes never responds)
        if sleepTime >= sleepTotal:
            mess = "WARN Over " + str(sleepTotal) + " seconds elapsed since download request.\n" + \
                "  Submitting new download request."
            printMess(mess, logFile)
            DownloadArchiveFile( fileDict, destination ) 
            sleepTime = 0

def SummarizeArchiveResponse( fileList, logFile=None ):
    """
    Return a table summary of the archive response as a string.

    * fileList = List of file dictionaries returned by ParseArchiveResponse
    * logFile = ObitTalk log file
    """
    # Generate summary table
    formatHead = "%-2s %-6s %-3s %-3s %-7s %-18s %-18s %-8s %-9s\n"
    table = formatHead % \
        ( "#-", "PCODE-", "SES", "SEG", "RCVR---", "STARTTIME---------", "STOPTIME----------", "SIZE----", "A-FILE-ID" )
    for i,file in enumerate(fileList):
        formatStr = "%2d %6s %3s %3s %7s %18s %18s %8s %9s\n" 
        wavelength = VLBACal.VLBAGetBandWavelength(file)
        table += formatStr % ( i, file['project_code'], 
            VLBACal.VLBAGetSessionCode( file ), file['segment'], 
            wavelength, file['starttime'], 
            file['stoptime'], file['FILESIZE_UNIT'], file['arch_file_id'] )
    return table

def XMLSetAttributes( element, nameValList ):
    """
    Add a sequence of name-value pairs as attributes to an xml.dom.minidom element. 
    
    Makes adding multiple attributes to an element easier.
    
    * element = xml.dom.minidom element
    * nameValList = list of name-value pairs to be added as attributes to 
      element
    """
    for pair in nameValList:
        # xml.dom.minidom.Element.setAttribute() must be given strings,
        # otherwise an error is produced.
        element.setAttribute( str(pair[0]), str(pair[1]) )

def XMLAddDescription( element, textDesc ):
    """
    Add VOTable description element to a xml.dom.minidom element.

    * element = xml.dom.minidom element
    * textDesc = string containing description
    """
    doc = xml.dom.minidom.Document()
    d = doc.createElement( "description" )
    tx = doc.createTextNode( textDesc )
    d.appendChild(tx)
    element.appendChild(d)

class AlarmException(Exception):
    pass

def alarmHandler(signum, frame):
    raise AlarmException

def nonBlockingRawInput(prompt='', timeout=60, logFile=None):
    """
Write *prompt* and wait a maximum of *timeout* seconds for user input.

* prompt = prompt for user input
* timeout = seconds to wait before proceeding without input
    """
    signal.signal(signal.SIGALRM, alarmHandler)
    signal.alarm(timeout)
    try:
        text = raw_input(prompt)
        signal.alarm(0)
        return text
    except AlarmException:
        print "\n"
        mess = "INFO Prompt timeout. Continuing..."
        printMess(mess, logFile)
    signal.signal(signal.SIGALRM, signal.SIG_IGN)
    return ''

def CompareFITS( fitsFile1, fitsFile2, err ):
    """
Compare 2 fits files.

* fitsFile1 = path to first FITS file 
* fitsFile2 = path to second FITS file
    """
    image1 = Image.newPFImage('image1', fitsFile1, 0, True, err, True)
    image2 = Image.newPFImage('image2', fitsFile2, 0, True, err, True)
    compList = Image.PCompare( image1, image2, err )
    return compList

def CompareFITSDir( dir1, dir2, pattern, err):
    """
Compare the FITS files matching *pattern* in *dir1* and *dir2*.

* dir1, dir2 = directories to use for comparison
* pattern = Unix shell pattern matching some FITS files
* err = OErr object
    """
    print("'Image 1' is in: " + dir1 )
    print("'Image 2' is in: " + dir2 )
    os.chdir( dir1 )
    fitsList1 = glob.glob( pattern )
    fitsList1.sort()
    os.chdir( dir2 )
    fitsList2 = glob.glob( pattern )
    fitsList2.sort()
    intersec = set( fitsList1 ) & set( fitsList2 )
    symDiff  = set( fitsList1 ) ^ set( fitsList2 )
    if len(symDiff) != 0:
        print("These files are not in both directories:")
        pprint.pprint(symDiff)
    table = []
    for f in intersec:
        path1 = dir1 + '/' + f
        path2 = dir2 + '/' + f
        row = CompareFITS( path1, path2, err )
        # Max Absolute Difference as a percentage of the Max Absolute in Image 1
        MaxAbsDiffPcnt = row[1] / row[0] * 100
        # RMS Difference as a percentage of the Max Absolute Difference
        if row[1] != 0:
            RMSDiffPcnt = row[2] / row[1] * 100
        else:
            RMSDiffPcnt = -1.0
        row.insert( 0, f )
        row.insert( 3, MaxAbsDiffPcnt )
        row.append( RMSDiffPcnt )
        table.append( row )
    format1 = "%-30.30s | %-10s %-10s %-3s %-10s %-3s"
    format2 = "%30.30s | %10.2e %10.2e %3.0f %10.2e %3.0f"
    print( format1 % ("Filename", "MaxAbsImg1", "MaxAbsDiff", "%", "RMS Diff", "%") )
    print( format1 % ('-'*30, '-'*10, '-'*10, '-'*3, '-'*10, '-'*3) )
    for row in table:
        print( format2 % tuple(row) )

def CompareUV( uvFile1, uvFile2, err, verbose=True  ):
    """
Compare UV FITS files *uvFile1* and *uvFile2*.

* uvFile1, uvFile2 = UV FITS files to be compared
* err = OErr object
    """
    uv1 = UV.newPFUV( 'uv1', uvFile1, 0, True, err )
    uv2 = UV.newPFUV( 'uv2', uvFile2, 0, True, err )
    rms = UV.PUtilVisCompare( uv1, uv2, err )
    if verbose:
        print("UV data set 1: " + uvFile1)
        print("UV data set 2: " + uvFile2)
    print("RMS of real, imag differences / amplitude of data set 2 =\n%6i" %
        ( rms ) )

def CompareUVDir( dir1, dir2, pattern, err ):
    """
Compare UV data files matching *pattern* in *dir1* and *dir2*.
*pattern* should match a single file in each directory.

* dir1, dir2 = directories to use for comparison
* pattern = Unix shell pattern matching a single UV file in each directory
* err = OErr object
    """
    os.chdir( dir1 )
    file1 = glob.glob( pattern )
    os.chdir( dir2 )
    file2 = glob.glob( pattern )
    if ( len(file1) != 1 or len(file2) != 1 ):
        print("Input pattern does not produce a unique match.")
        print("dir1 matches to " + str(file1) )
        print("dir2 matches to " + str(file2) )
        return
    filePath1 = dir1 + '/' + file1[0]
    filePath2 = dir2 + '/' + file2[0]
    CompareUV( filePath1, filePath2, err )

def TestPipe( dir1, dir2, err ):
    """
    Test pipeline by comparing pipeline output in *dir1* with output in *dir2*.
    *dir1* and *dir2* could be, for example, output directories for two different
    versions of Obit.
    
    * dir1, dir2 = directories to use for comparison
    * err = OErr object
    """
    dir1 = os.path.abspath( dir1 )
    dir2 = os.path.abspath( dir2 )
    print("Testing calibrated and averaged UV data.")
    CompareUVDir( dir1, dir2, '*CalAvg.uvtab', err )
    print("Testing FITS images.")
    CompareFITSDir( dir1, dir2, '*IClean.fits', err )

def getStartStopTime( uv, err ):
    """
    Return the start and stop times of a uv data set as a tuple.

    The times are returned in units of MJD.

    * uv = Obit UV data object
    * err = OErr object
    """
    # Get MJD of the reference date
    calDate = uv.Desc.Dict["obsdat"]
    MJD = UVDesc.PDate2JD( calDate ) - 2400000.5

    # Get the data set start and stop times
    nx = uv.NewTable(Table.READONLY, 'AIPS NX', 0, err)
    nxNrow = nx.Desc.Dict['nrow'] # last row
    nx.Open(Table.READONLY, err)
    row1 = nx.ReadRow( 1, err )
    rowN = nx.ReadRow( nxNrow, err )
    tInt = row1['TIME INTERVAL'][0] # scan duration
    t1 = row1['TIME'][0] - tInt # 1st  scan center time
    t2 = rowN['TIME'][0] + tInt # last scan center time
    nx.Close(err)
    tStart = t1 + MJD
    tStop = t2 + MJD
    return (tStart, tStop)

def validate( dataDir, archDir = '../archive', 
    archBkup = '/export/home/cv-pipe-a/jcrossle/VLBAPipeProducts/archive_backup', 
    group = 'vlbapipe'):
    """
    Validate a data set and move it to the archive staging area.

    This function should be run after the data set has been examined and 
    determined to be valid.  The procedure is as follows:
    
    1) The data set, *dataDir*, is moved to the archive staging area,
       *archDir*. 
    2) If *archBkup* is given, the *dataDir* is also copied to the archive
       backup area, *archBkup*.
    3) If *group* is given, all files moved to the archive staging area have
       their group changed to *group*, and group read/write/access permissions
       are set. 

    * dataDir = data set directory
    * archDir = archive staging area (../archive, by default)
    * archBkup = archive backup directory (optional)
    * group = Linux group name to be set for all files and directories
      (optional)
    """

    import grp, shutil

    # Normalize paths
    dataDir = os.path.abspath( dataDir )
    archDir = os.path.abspath( archDir )

    # Verify existence of files / dirs.
    if not os.path.exists( dataDir ):
        raise IOError( (1, 'File does not exist', dataDir) )
    if not os.path.exists( archDir ):
        raise IOError( (1, 'Directory does not exist', archDir) )

    # Copy dataDir to archive backup directory
    if archBkup:
        archBkup = os.path.abspath( archBkup )
        if not os.path.exists( archBkup ):
            raise IOError( (1, 'Directory does not exist', archBkup) )
        base = os.path.basename( dataDir )
        newDataBkup = os.path.join( archBkup, base )
        if os.path.exists( newDataBkup ):
            mess = "INFO Removing pre-existing data: " + newDataBkup
            printMess(mess, logFile)
            shutil.rmtree( newDataBkup )
        mess = "INFO Copying data to archive backup directory:\n  " + dataDir + \
            " --> " + newDataBkup
        printMess(mess, logFile)
        shutil.copytree( dataDir, newDataBkup )

    # Get archive file ID for bookkeeping.
    projDataFile = glob.glob( dataDir + '/*ProjReport.pickle' )
    projData = FetchObject( projDataFile[0] )
    archFileID = projData['archFileID']

    # Move data set to archive staging directory
    newDataDir = os.path.join( archDir, os.path.basename( dataDir ) )
    if os.path.exists( newDataDir ):
        mess = "INFO Removing pre-existing data: " + newDataDir
        printMess(mess, logFile)
        shutil.rmtree( newDataDir )
    mess = "INFO Moving data to archive staging area:\n  " + \
        dataDir + " --> " + newDataDir 
    printMess(mess, logFile)
    shutil.move( dataDir, newDataDir )
   
    # Set group and group read/write/access permissions in staging area
    if group:
        mess = "INFO Setting group and group read/write/access permissions."
        printMess(mess, logFile)
        gid = grp.getgrnam( group )[2]
        os.chown( newDataDir, -1, gid )
        for root, dirs, files in os.walk( newDataDir ):
            os.chown( root, -1, gid )
            os.chmod( root, 0775 )
            for dir in dirs:
                path = os.path.join( root, dir )
                os.chown( path, -1, gid )
                os.chmod( path, 0775 )
            for file in files:
                path = os.path.join( root, file )
                os.chown( path, -1, gid )
                os.chmod( path, 0664 )

def getSVNVersion(path):
    """
    get subversion revision number for a given path

    * path = path to directory or file in question
    """
    # Get revision number
    cmd = 'svnversion -n ' + path
    f = os.popen(cmd)
    ver = f.read()
    print('SVN version of '+path+' is ' + ver)
    return ver
# end getSVNVersion

def dateStringToMJD( date ):
    """
    Convert date-time string returned by archive to MJD float.

    * date = archive date-time string
    """
    pattern = re.compile(r'([0-9]{2})-([A-Z][a-z]{2})-([0-9]{2}) ([0-9]{2}):([0-9]{2}):([0-9]{2})')
    match = re.match( pattern, date )
    if match:
        year = int(match.group(1))
        if year < 90: year += 2000
        else: year += 1900
        monthStr = match.group(2)
        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct',
                  'Nov','Dec']
        month = months.index( monthStr )
        day  = int(match.group(3))
        hour = int(match.group(4))
        min  = int(match.group(5))
        sec  = int(match.group(6))
    else:
        return none
    m = mjd.mjd()
    return m.mjd_now( month, day, year, hour, min, sec )
