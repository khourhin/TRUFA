#! /usr/bin/env python

# THINGS TO IMPROVE:

# THINGS TO FIX:
# if bowtie2 directly with cufflinks or express (directly from assembly) >>> folder created in .cache/tmp
# >>> this has been fixed but clumsy in bowtie2.cmd

# THINGS TO INSTALL:
#CDHITEST

# THINGS TO IMPROVE:
# in bowtie 2 command, check the output files names (the first linesof the cmd)
# remove env variables (not used the same way anymore) <<< not sure about that
# Make better the import of the parameters (without having to delete the other entries in sort_parameters)

# THINGS TO VERIFY (TESTING PARAMETERS NOT CORRECT FOR REAL USE)
# input files (reads)

#-------------------------------------------------------------------------------
import logging
import logging.handlers
import sys
import os
import getopt
import mimetypes
from lib import submiting_jobs as sj
from lib import soft_data
from lib import config
from lib import run_config
#from lib import common_fun

#-------------------------------------------------------------------------------
def configLog():
    # get logger
    logger = logging.getLogger()
    
    # create file handler
    ch = logging.handlers.RotatingFileHandler( config.LOGFILE, mode='a', maxBytes=config.LOGFILEBYTES, backupCount=5 )
    
    ch.setLevel( logging.DEBUG )
    
    # create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s -%(levelname)s- %(message)s',
        datefmt='%Y%m%d %H:%M:%S' )
    
    # add formatter to ch
    ch.setFormatter( formatter )
    
    # add ch to logger
    logger.addHandler( ch )
    
    logging.captureWarnings( True )

#-------------------------------------------------------------------------------
def checkIfCommandLine():
    """ Check if command line or webserver version.
    For command line: edit run_config in lib and launch ./pipe_launcher -c """
    try:
        opts, args = getopt.getopt(sys.argv[1:], "c")
    except getopt.GetoptError as err:
        print str(err)
        sys.exit(2)
        
    for o, a in opts:
        if o == "-c":
            return True
        else:
            return False
            
#-------------------------------------------------------------------------------
def setUidJid(COMMAND_MODE):
    if COMMAND_MODE:
        print "Launching in command line mode"
        REALUSER = run_config.REALUSER
        job_num = run_config.JOB_NUM
        para_dict = run_config.para_dict
        DEBUG = run_config.DEBUG
        #    common_fun.check_inputs_format(para_dict)
    
    else: # if run by webserver
        print "Launched by the webserver"
        DEBUG = False
        REALUSER, para_dict = sj.get_parameters(sys.argv[1],sys.argv[2])
        job_num = sys.argv[-1]

    return REALUSER, job_num, para_dict, DEBUG

#-------------------------------------------------------------------------------
def setPaths():
    OUT_FOLDER = config.OUT_FOLDER + REALUSER + "/jobs/Job_" + job_num + "/"
    DATA_FOLDER = config.OUT_FOLDER + REALUSER + "/data/"

    folders_dict = dict(OUT_FOLDER = OUT_FOLDER,
                        DATA_FOLDER = DATA_FOLDER,
                        CACHE_PATH = OUT_FOLDER + ".cache/",
                        CLEANING_FOLDER = OUT_FOLDER + "CLEANING/",
                        STAT_FOLDER = OUT_FOLDER + "STAT/",
                        ASSEMBLY_MAPPING_FOLDER = OUT_FOLDER + "ASSEMBLY_MAPPING/",
                        IDENTIFICATION_FOLDER = OUT_FOLDER + "IDENTIFICATION/",
                        EXPRESSION_FOLDER = OUT_FOLDER + "EXPRESSION/",
                        PIPE_PATH = config.PIPE_PATH,
                        PY_BIOLIB_PATH = config.PY_BIOLIB_PATH,
                        COMMAND_PATH = config.COMMAND_PATH)

    COMMAND_PATH = config.COMMAND_PATH
    BLAST_DB_FOLDER = config.BLAST_DB_FOLDER
    HMMER_PROFILE_FOLDER = config.HMMER_PROFILE_FOLDER

    return folders_dict, COMMAND_PATH, BLAST_DB_FOLDER, HMMER_PROFILE_FOLDER

#-------------------------------------------------------------------------------
def makeOutputFolders(folders_dict):

    try:
        os.makedirs(folders_dict["OUT_FOLDER"])
        os.makedirs(folders_dict["CACHE_PATH"])
        os.mkdir(folders_dict["CACHE_PATH"] + "tmp")
        os.mkdir(folders_dict["STAT_FOLDER"])

    except Exception as e:
        logging.error(e)
        sys.exit()

#-------------------------------------------------------------------------------
def getInput(para_dict):
    input_dict = sj.sort_parameters(para_dict)
    READS_FILES = input_dict["reads_files"]
    READS_FILES_COUNT = len(READS_FILES)
    BLATN_CUSTOM_READS = input_dict["blatn_reads"]
    BLATN_CUSTOM_ASS = input_dict["blatn_ass"]
    BLATX_CUSTOM_ASS = input_dict["blatx_ass"]
    HMMER_CUSTOM_DB = input_dict["hmm_custom_db"]

    return input_dict, READS_FILES, READS_FILES_COUNT, BLATN_CUSTOM_READS,BLATN_CUSTOM_ASS, BLATX_CUSTOM_ASS, HMMER_CUSTOM_DB

#-------------------------------------------------------------------------------
def setBashEnv(input_dict, folders_dict):
    env = sj.set_environment(input_dict, folders_dict)
    env["MINIMAL_OUTPUT"]=config.MINIMAL_OUTPUT
    
    # Add for MPIBLAST:
    #env["BLASTMAT"]="/mnt/seq_dbs/matrices"
    #env["MPIBLAST_SHARED"]="/mnt/seq_dbs/nr"
    #env["MPIBLAST_LOCAL"]=folders_dict["IDENTIFICATION_FOLDER"] + ""

    return env

#-------------------------------------------------------------------------------
def checkIfCompressedReads(folders_dict, READS_FILES):
    new_READS_FILES = []

    with open(folders_dict["OUT_FOLDER"] + ".tmp1.txt", "a") as f:
        files_to_unzip = []

        for rf in READS_FILES:
            raw = rf
            rf = rf.split( os.extsep, 2 )
            fname = ".".join( rf[:2] )
            ext = rf[-1]

            # Check extension:
            if ext in ["gz","tar.gz"]:
                f.write("File: {0} is set for extraction\n".format(raw))
                files_to_unzip.append(raw)
                new_READS_FILES.append(fname)
            else:
                f.write("""File: {0} doesn't seem to be a compressed file,
                        or his extension is not recognized, so it will be considered
                        as a 'directly usable' file\n""".format(raw))
                new_READS_FILES.append(raw)

    return new_READS_FILES, files_to_unzip

#-------------------------------------------------------------------------------
def extract(files_to_unzip, OUT_FOLDER, COMMAND_PATH, dep):
    env["FILES_TO_UNZIP"] = "'" + " ".join(files_to_unzip) + "'"
    job_id = sj.make_and_submit_job(OUT_FOLDER,
                                    COMMAND_PATH + "extract2.cmd",
                                    "extract", 1,
                                    1, "12:00:00","", env)
#    slurm_ids.append(job_id)
    dep.append(job_id)
    return dep

#-------------------------------------------------------------------------------
class TrufaJob():
    """
    To define better names
    HERE:
    jobfolder is for the whole Job, composed of TrufaJobs e.g; OUT_FOLDER
    outfolder is the outfolder of the TrufaJob: STAT_FOLDER/fastqc_report
    """
    def __init__(self, name, command, dep, jobfolder, ntasks, ncpus, tlim, env, outfolder=None):
        self.name = name
        self.command_path = config.COMMAND_PATH + command
        self.dep = dep
        self.jobfolder = jobfolder
        self.outfolder = outfolder
        self.ntasks = ntasks
        self.ncpus = ncpus
        self.tlim = tlim
        self.env = env

    def makeOutFolder(self):
        if self.outfolder:
            if not os.path.exists(self.outfolder):
                os.makedirs(self.outfolder)
            else:
                print self.name
                print self.outfolder + " already exists: not created (it's fine)."

    
    def script(self):
        sj.make_script(self.jobfolder,
                                       	self.command_path,
                                       	self.name,
                                       	self.ntasks,
                                       	self.ncpus,
                                        self.tlim,
                                        self.dep,
                                       	self.env,
                                        DEBUG)
        


    def submit(self):
        job_id = sj.make_and_submit_job(self.jobfolder,
                                        self.command_path,
                                        self.name,
                                        self.ntasks,
                                        self.ncpus,
                                        self.tlim,
                                        self.dep,
                                        self.env,
                                        DEBUG)
        
        return job_id

#-------------------------------------------------------------------------------
def prepareAndSubmit( jobname, cmd, dep, jobfolder, ntasks, cpus, tlim, env, outfolder=None):
    """
    Prepare the outfolders and submit a TrufaJob
    """

    try:

        job = TrufaJob( jobname, cmd, dep, jobfolder, ntasks, cpus, tlim, env, outfolder)
        job.makeOutFolder()
        slurm_id = job.submit()

    except Exception as e:
        logging.error(e)
        sys.exit()
        
    return slurm_id

#------------------------------------------------------------------------------
def prepareScript( jobname, cmd, dep, jobfolder, ntasks, cpus, tlim, env, outfolder=None):
    """
    Prepare the outfolders and submit a TrufaJob
    """
    try:
        scripttrufa = TrufaJob( jobname, cmd, dep, jobfolder, ntasks, cpus, tlim, env, outfolder)
        
        scripttrufa.script()

    except Exception as e:
        logging.error(e)
        sys.exit()
        
    return slurm_id


    
#-------------------------------------------------------------------------------
def setReadOut( names_in, suffix):
    """ To setup the names of the output for the cleaning steps
    """
    # Setup the reads files basenames for the cleaning outputs
    
    names_in = names_in.replace("'", "").split(" ")
    ext = [ os.path.splitext(x)[-1] for x in names_in ]
    basenames = [ os.path.splitext(os.path.basename(x))[0]
                       for x in names_in ]
    names_out = "'" + " ".join( [ x + suffix + y
                                  for x, y in zip(basenames, ext) ] ) + "'"

    return names_out

#-------------------------------------------------------------------------------
# MAIN
#-------------------------------------------------------------------------------
logging.getLogger().setLevel( logging.DEBUG )
configLog()
logging.info("Start server side")
    
# INIT VAR: # Not in the same line  because of issues with values assignments 
slurm_ids = []
dep = []
blat_dep = []
hmmer_dep = []
b2go_dep = []
expr_dep = []

COMMAND_MODE = checkIfCommandLine()
REALUSER, job_num, para_dict, DEBUG = setUidJid(COMMAND_MODE)
folders_dict, COMMAND_PATH, BLAST_DB_FOLDER, HMMER_PROFILE_FOLDER = setPaths()
makeOutputFolders(folders_dict)
input_dict, READS_FILES, READS_FILES_COUNT, BLATN_CUSTOM_READS,BLATN_CUSTOM_ASS, BLATX_CUSTOM_ASS, HMMER_CUSTOM_DB = getInput(para_dict)

steps = input_dict["progs"]
env = setBashEnv(input_dict, folders_dict)

# Make LOG for debugging
sj.make_log(REALUSER, input_dict, folders_dict["OUT_FOLDER"] + ".tmp1.txt")

# Check and file decompression
new_READS_FILES, files_to_unzip = checkIfCompressedReads(folders_dict, READS_FILES)

if files_to_unzip and not DEBUG:
    dep = extract(files_to_unzip, folders_dict["OUT_FOLDER"], COMMAND_PATH, dep)

# Resetting READS_FILES variable to point to extracted files
env["READS_FILES"] = "'" + " ".join(new_READS_FILES) + "'"

#-------------------------------------------------------------------------------
print "Antes de fastqc"    
if "FASTQC1" in steps:
    #Generate the docker job
    slurm_id = prepareAndSubmit("fastqc",
                                "dockers/fastqc.cmd",
                                dep,
                                folders_dict["OUT_FOLDER"],
                                READS_FILES_COUNT,2,"03:00:00",env,
                                folders_dict["STAT_FOLDER"] + "fastqc_report")
    prepareScript("fastqc",
                                "cleaning/larafastqc.cmd",
                                dep,
                                folders_dict["OUT_FOLDER"],
                                READS_FILES_COUNT,2,"03:00:00",env,
                                folders_dict["STAT_FOLDER"] + "fastqc_report")

    slurm_ids.append( slurm_id )
    
    
    # Fastqc doesn't have to be incorporated in the dependency list

#-------------------------------------------------------------------------------
# If any program of the cleaning step is on:
if soft_data.cleaning_progs & steps:

    os.mkdir(folders_dict["CLEANING_FOLDER"])
#-------------------------------------------------------------------------------
    print "Antes de cutadapt   "
    if "CUTADAPT" in steps:

        env["READS_OUT"] = setReadOut( env["READS_FILES"], "_noad" )

        slurm_id = prepareAndSubmit("cutadapt",
                                    "dockers/cutadapt.cmd",
                                    dep,
                                    folders_dict["OUT_FOLDER"],
                                    READS_FILES_COUNT,16,"06:00:00", env)
        
        prepareScript("cutadapt",
                                "cleaning/laracutadapt.cmd",
                                dep,
                                folders_dict["OUT_FOLDER"],
                                READS_FILES_COUNT,16,"06:00:00", env)

        
        slurm_ids.append(slurm_id)
        dep.append(slurm_id)

        # Set input for next step:
        env["READS_FILES"] = env["READS_OUT"]

#-------------------------------------------------------------------------------
    print "ANTES DE  DUP"    
    if "DUP" in steps:
	
        env["READS_OUT"] = setReadOut( env["READS_FILES"], "_nodup" )
        slurm_id = prepareAndSubmit("dup_prinseq",
                                    "dockers/prinseq_dup.cmd",
                                    dep,
                                    folders_dict["OUT_FOLDER"],
                                    1, 16, "24:00:00", env)
        prepareScript("dup_prinseq",
                                    "cleaning/laraprinseq_dup.cmd",
                                    dep,
                                    folders_dict["OUT_FOLDER"],
                                    1, 16, "24:00:00", env)

        slurm_ids.append(slurm_id)
        dep.append(slurm_id)

        # Set input for next step:
        env["READS_FILES"] = env["READS_OUT"]

#-------------------------------------------------------------------------------
    print " ANTES DE TRIM!!!!!!!!!!!!!! " 
    if "TRIM" in steps:

        env["READS_OUT"] = setReadOut( env["READS_FILES"], "_trim" )

        slurm_id = prepareAndSubmit("trim_prinseq",
                                    "dockers/prinseq_trim.cmd",
                                    dep,
                                    folders_dict["OUT_FOLDER"],
                                    READS_FILES_COUNT, 16, "72:00:00", env)

        prepareScript("trim_prinseq",
                                    "cleaning/laraprinseq_trim.cmd",
                                    dep,
                                    folders_dict["OUT_FOLDER"],
                                    READS_FILES_COUNT, 16, "72:00:00", env)


        slurm_ids.append(slurm_id)
        dep.append(slurm_id)

        # Set input for next step:
        env["READS_FILES"] = env["READS_OUT"]

#-------------------------------------------------------------------------------
    print "=========================================== 1 ==========================================="
    print soft_data.blat_reads_progs
    print "=========================================== 2 ============================================"
    print steps
# if there is any BLAT for the reads:
    if soft_data.blat_reads_progs & steps:
        env["READS_OUT"] = setReadOut( env["READS_FILES"], "_blat" )

    # Convert to fasta:
        slurm_id = prepareAndSubmit("fq2fas",
                                    "dockers/fq2fas.cmd",
                                    dep,
                                    folders_dict["OUT_FOLDER"],
                                    READS_FILES_COUNT, 4, "1:00:00", env)

        prepareScript("fq2fas",
                                    "cleaning/larafq2fas.cmd",
                                    dep,
                                    folders_dict["OUT_FOLDER"],
                                    READS_FILES_COUNT, 4, "1:00:00", env)
        slurm_ids.append(slurm_id)
        dep.append(slurm_id)

    # Split for faster BLAT:
        slurm_id = prepareAndSubmit("split4rblat",
                                    "dockers/splitting.cmd",
                                    dep,
                                    folders_dict["OUT_FOLDER"],
                                    READS_FILES_COUNT, 4, "1:00:00", env)
        prepareScript("split4rblat",
                                    "cleaning/larasplitting.cmd",
                                    dep,
                                    folders_dict["OUT_FOLDER"],
                                    READS_FILES_COUNT, 4, "1:00:00", env)
        slurm_ids.append(slurm_id)
        dep.append(slurm_id)

#-------------------------------------------------------------------------------
        if "BLAT_UNIVEC" in steps:
            print " ENTRA AQUI TRANQUILAMENTE             !!!!!!!!!!!!!!!!!!!!!!!!!!!!"       
            env["BLAT_READS_DB"] = BLAST_DB_FOLDER + "univec/univec"
            env["BLAT_TYPE"] = "'-t=dna -q=dna'"

            slurm_id = prepareAndSubmit("rblat_univec",
                                        "cleaning/blat.cmd",
                                        dep,
                                        folders_dict["OUT_FOLDER"],
                                        READS_FILES_COUNT * 32, 1, "6:00:00", env)

            slurm_ids.append(slurm_id)
            blat_dep.append(slurm_id)


#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
        if "BLAT_ECOLI" in steps:

            env["BLAT_READS_DB"] = BLAST_DB_FOLDER + "E_coli_G/E_coli_G"
            env["BLAT_TYPE"] = "'-t=dna -q=dna'"

            slurm_id = prepareAndSubmit("rblat_ecoli",
                                        "cleaning/blat.cmd",
                                        dep,
                                        folders_dict["OUT_FOLDER"],
                                        READS_FILES_COUNT * 32, 1, "6:00:00", env)

            slurm_ids.append(slurm_id)
            blat_dep.append(slurm_id)

#-------------------------------------------------------------------------------
        if "BLAT_SCERE" in steps:

            env["BLAT_READS_DB"] = BLAST_DB_FOLDER + "S_cerevisiae_G/S_cerevisiae_G"
            env["BLAT_TYPE"] = "'-t=dna -q=dna'"

            slurm_id = prepareAndSubmit("rblat_scere",
                                        "dockers/blat.cmd",
                                        dep,
                                        folders_dict["OUT_FOLDER"],
                                        READS_FILES_COUNT * 32, 1, "6:00:00", env)
            prepareScript("rblat_scere",
                                        "cleaning/larablat.cmd",
                                        dep,
                                        folders_dict["OUT_FOLDER"],
                                        READS_FILES_COUNT * 32, 1, "6:00:00", env)

            slurm_ids.append(slurm_id)

#------------------------------------------------------------------------------
        if "BLAT_CUSTOM_READS" in steps:
            for db in BLATN_CUSTOM_READS:
                env["BLAT_READS_DB"] = DATA_FOLDER + db
                env["BLAT_TYPE"] = "'-t=dna -q=dna'"

                slurm_id = prepareAndSubmit("rblat_" + db,
                                            "dockers/blat.cmd",
                                            dep,
                                            folders_dict["OUT_FOLDER"],
                                            READS_FILES_COUNT * 32, 1, "6:00:00", env)
                prepareScript("rblat_" + db,
                                            "cleaning/larablat.cmd",
                                            dep,
                                            folders_dict["OUT_FOLDER"],
                                            READS_FILES_COUNT * 32, 1, "6:00:00", env)

                slurm_ids.append(slurm_id)
                blat_dep.append(slurm_id)


#-------------------------------------------------------------------------------
# CLEANING FROM BLAT HITS:

        slurm_id = prepareAndSubmit("blat_parser",
                                    "dockers/blat_parser.cmd",
                                    blat_dep,
                                    folders_dict["OUT_FOLDER"],
                                    1, 16, "2:00:00", env)
        prepareScript("blat_parser",
                                    "cleaning/larablat_parser.cmd",
                                    blat_dep,
                                    folders_dict["OUT_FOLDER"],
                                    1, 16, "2:00:00", env)

        slurm_ids.append(slurm_id)
        dep.append(slurm_id)

        slurm_id = prepareAndSubmit("reads_removal",
                                    "dockers/reads_removal.cmd",
                                    dep,
                                    folders_dict["OUT_FOLDER"],
                                    1, 1, "3:00:00", env)
        prepareScript("reads_removal",
                                    "cleaning/larareads_removal.cmd",
                                    dep,
                                    folders_dict["OUT_FOLDER"],
                                    1, 1, "3:00:00", env)

        slurm_ids.append(slurm_id)
        dep.append(slurm_id)

        # Set input for next step:
        env["READS_FILES"] = env["READS_OUT"]


#-------------------------------------------------------------------------------
# Pointing to clean reads files
# If a cleaning has been first performed have to add the CLEANING_FOLDER PATH
if soft_data.cleaning_progs & steps:

    reads_tmp =  env["READS_FILES"].replace("'", "").split()
    env["READS_FILES"] = "'" + " ".join([ folders_dict["CLEANING_FOLDER"] + x
                          for x in reads_tmp ]) + "'"

#-------------------------------------------------------------------------------
if "FASTQC2" in steps:

    slurm_id = prepareAndSubmit("fastqc",
                                "cleaning/fastqc.cmd",
                                dep,
                                folders_dict["OUT_FOLDER"],
                                READS_FILES_COUNT, 2, "03:00:00", env,
                                folders_dict["STAT_FOLDER"] + "fastqc_report")
    slurm_ids.append( slurm_id )

    # Fastqc doesn't have to be incorporated in the dependency list

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
        
# print list of SLURM IDS:
if not DEBUG:
    print "slurmids: " + ",".join(slurm_ids)
