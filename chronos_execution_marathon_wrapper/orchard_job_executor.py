#!/usr/bin/env python3

import configparser
import random
import os
import subprocess
import argparse
import sys
import shlex
import time
from datetime import datetime
from subprocess import check_call

def readCfgOptions(section):
  cfgOptions = dict()

  for param in section:
    try: 
      cfgOptions[param] = section.get(param)
      if cfgOptions[param] == -1:
        ebugPrint("skip: %s" % param)
    except:
      print("exception on %s!" % param)
      cfgOptions[param] = None
  return(cfgOptions)

def buildCommandString(params, executor):
  execString = []

  if executor == 'spark':
    execString.append('/usr/bin/timeout {}'.format(params.get('timeout')))
    execString.append(params.get('sparkexec'))
    execString.append('--master {}'.format(params.get('mesosmasters')))
    execString.append('--conf spark.ui.port={}'.format(os.environ.get('PORT0','312' + str(random.randint(10,99)))))
    execString.append('--conf spark.mesos.coarse=true')
    execString.append('--conf spark.mesos.extra.cores={}'.format(params.get('cores')))
    execString.append('--conf spark.cores.max={}'.format(params.get('coresmax')))
    execString.append('--conf spark.mesos.constraints="rack:spark"')
    execString.append('--conf spark.sql.tungsten.enabled={}'.format(params.get('sparksqltungsten','true')))
    execString.append('--class {}'.format(params.get('classname')))
    execString.append('--total-executor-cores {}'.format(params.get('cores')))
    execString.append('--driver-memory {}'.format(params.get('memory')))
    execString.append('--executor-memory {}'.format(params.get('memory')))
    execString.append('--jars {} {} {}'.format(params.get('classpath'), params.get('jarfile'), params.get('optargs')))

  if executor == 'java':
    execString.append('/usr/bin/timeout {}'.format(params.get('timeout')))
    execString.append(params.get('javaexec'))
    execString.append('-Xmx{}'.format(params.get('memory')))
    execString.append('-XX:+UseConcMarkSweepGC')
    execString.append('-XX:+CMSClassUnloadingEnabled')
    execString.append('-XX:+CMSParallelRemarkEnabled')
    execString.append('-XX:+PrintCommandLineFlags')
    execString.append('-Xss16M')
    execString.append('-Duser.timezone=GMT')
    execString.append('-cp {}:{}'.format(params.get('jarfile'), params.get('classpath')))
    execString.append(params.get('classname'))

  return execString

def executeJob(commandString, jarFile, job):
  print("\n*********************** Starting JOB: {} using SHA: {} ***********************" \
    .format(job, os.path.basename(jarFile)))
  print("\n{}\n".format(" ".join(commandString)))

  try: 
    start_time = datetime.now()
    check_call(shlex.split(" ".join(commandString)))
    returncode = 0
    end_time = datetime.now()

    print('\nJob {} completed successfully total runtime was {}\n'.format(job,end_time - start_time))
  except subprocess.CalledProcessError as e:
    print("\n{} failed with returncode {} exiting.".format(job,e.returncode))
    sys.exit(e.returncode)

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Orchard Batch Job Executor v1")
  parser.add_argument("-j", "--jobname", help="Name of Chronos Job to run", required=False)
  parser.add_argument("-l", "--listjobs", action="store_true", help="List all available jobs", required=False)
  args = parser.parse_args()

  cfgFile = "/data/orchard/etc/loader_jobs.cfg"
  config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
  commandString = {}

  if not args.jobname and not args.listjobs:
    parser.print_help()
    sys.exit(-1)

  if not os.access(cfgFile, os.R_OK):
    sys.stderr.write("Fatal error: {} is not readable\n".format(cfgFile))
    sys.exit(-1)

  config.read(cfgFile)
  jobs = config.sections()

  if args.listjobs:
    jobs.remove('library')
    jobs.remove('spark')
    jobs.remove('java')
    for job in jobs: print(job)
    print("\n--------------\n{} jobs found".format(len(jobs)))
    sys.exit(0)

  if not args.jobname in jobs: 
    sys.stderr.write("Fatal error: job \"{}\" not found in {}\n".format(args.jobname, cfgFile))
    sys.exit(-1)

  print("Found {} jobs definitions in {}".format(len(jobs)-2, cfgFile))

  for job in jobs:
    if job == 'spark':
      sparkDefaults = readCfgOptions(config[job])
      continue
    if job == 'java': 
      javaDefaults = readCfgOptions(config[job])
      continue
    if args.jobname == job:
      jobCfg = readCfgOptions(config[job])
      if jobCfg.get('executor') == 'spark':
        jobCfg = dict(sparkDefaults, **jobCfg)
        commandString = buildCommandString(jobCfg, 'spark')
        executeJob(commandString,jobCfg.get('jarfile'),job)
      if jobCfg.get('executor') == 'java':
        jobCfg = dict(javaDefaults, **jobCfg)
        commandString = buildCommandString(jobCfg, 'java')
        executeJob(commandString,jobCfg.get('jarfile'),job)
