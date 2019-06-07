#!/usr/bin/python
import os
import sys
import time
import getopt
import json
import math
import re
import threading
import subprocess

# Define needed directories and files
toolPath = os.path.split(os.path.realpath(__file__))[0]
nsdperfConfFile = "%s/nsdperfConf" % (toolPath)
nsdperfPath = "/tmp/nsdperf"
sshOption = "-o StrictHostKeyChecking=no"

# Log lock
LOG_LOCK = threading.Lock()

# Subroutines
def processArgs():
    confFile = open(nsdperfConfFile, "r")
    confFromFile = json.loads(confFile.read())
    confFile.close()
    for key in confFromFile.keys():
        if (not conf.has_key(key) or not conf[key]):
            conf[key] = confFromFile[key]

    if (not conf["nodelist"] and (not conf["server"] or not conf["client"])):
        halt("Error: you have to provide --nodelist or both --client and --server")
    if (conf["nodelist"] and conf["server"] and conf["client"]):
        log("Warning: you provided both --nodelist and --client --server, I'll use --client --server and ignore --nodelist")
        conf["nodelist"] = ""
    dupNodes = [i for i in conf["server"] if i in conf["client"]]
    if (dupNodes):
        halt("Error: %s cannot be server and client at the same time, there shouldn't be duplicated nodes in servers and clients" % dupNodes);
    allowedTests = ["write", "read", "nwrite", "swrite", "sread", "rw"]
    for test in conf["test"]:
        if (test not in allowedTests):
            halt("Error: unknown test <%s>, please choose from <%s>" % (test, allowedTests))
    if (not conf["test"]):
        conf["test"] = ["read", "nwrite"]

def createExecutable(node):
    [rc, out, err] = runcmd("ssh %s %s \"test -d %s\"" % (sshOption, node, nsdperfPath))
    if (rc):
        chkcmd("ssh %s %s \"mkdir -p %s\"" % (sshOption, node, nsdperfPath))
    else:
        [rc, out, err] = runcmd("ssh %s %s \"test -x %s\"" % (sshOption, node, nsdperfexe))
    cmd = ""
    if (rc or conf["rebuild"]):
        if (conf["rebuild"]):
            log("Force rebuild nsdperfexe on node %s as -r is specified" % (node))
        chkcmd("scp %s %s/nsdperf.C %s/makefile %s:%s/" % (sshOption, toolPath, toolPath, node, nsdperfPath))
        uname = chkcmd("ssh %s %s \"uname -a\"" % (sshOption, node))
        if (re.search("linux", uname, re.I)):
            [verbsh, out, err] = runcmd("ssh %s %s \"test -e /usr/include/infiniband/verbs.h\"" % (sshOption, node))
            [rdmacmh, out, err] = runcmd("ssh %s %s \"test -e /usr/include/rdma/rdma_cma.h\"" % (sshOption, node))
            if (verbsh or rdmacmh):
                log("INFO: verbs.h or rdma_cma.h could not be found. nsdperf could not support RDMA on node %s." % (node))
                log("Excluding RDMA in compilation.")
                cmd = "cd %s; g++ -O2 -o nsdperfexe -lpthread -lrt nsdperf.C" % (nsdperfPath)
            else:
                cmd = "cd %s; g++ -O2 -DRDMA -o nsdperfexe -lpthread -lrt -libverbs -lrdmacm nsdperf.C" % (nsdperfPath)
        # elif (re.search("AIX", uname, re.I)):
        #     cmd = "cd %s; make all" % (nsdperfPath)
        else:
            halt("Error: cannot compile %s/nsdperf.C on node $node, OS is not supported." % (nsdperfPath))
        log("INFO: building nsdperfexe on node %s" % (node))
        chkcmd("ssh %s %s \"%s\"" % (sshOption, node, cmd))
    else:
        log("INFO: skip building nsdperfexe on node %s as %s already exists. Use -r if you want to force rebuild." % (node, nsdperfexe))

def runTest(server, client):
    log("---------- Running nsdperf test with server %s client %s ----------" % (server, client))
    cliOptions = makeCmds(server, client)
    allNodes=[]
    allNodes.extend(server)
    allNodes.extend(client)
    threads = []
    for node in allNodes:
        thr = threading.Thread(target = startServerThr, args = (node, cliOptions))
        thr.start()
        threads.append(thr)
    for thr in threads:
        thr.join()

    output = chkcmdLiveOutput("%s -i %s %s" % (nsdperfexe, nsdperfCmdFile, cliOptions))
    parseOutput(server, client, output)

def makeCmds(server, client):
    cmdsInFile = ""
    cliOptions = ""
    joinStr = " "
    servers = joinStr.join(server)
    clients = joinStr.join(client)
    cmdsInFile = "server %s\nclient %s\n" % (servers, clients)
    if (conf["ttime"]):
        cmdsInFile = cmdsInFile + "ttime %s\n" % (conf["ttime"])
    if (conf["testerThr"]):
        cmdsInFile = cmdsInFile + "threads %s\n" % (conf["testerThr"])
    if (conf["buffsize"]):
        cmdsInFile = cmdsInFile + "buffsize %s\n" % (conf["buffsize"])
    if (conf["socksize"]):
        cmdsInFile = cmdsInFile + "socksize %s\n" % (conf["socksize"])
    for test in conf["test"]:
        cmdsInFile = cmdsInFile + "test %s\n" % (test)
    cmdsInFile = cmdsInFile + "killall\nquit"
    cmdFile = open(nsdperfCmdFile, 'w')
    cmdFile.write(cmdsInFile)
    cmdFile.close()

    if (conf["receiverThr"]):
        cliOptions = cliOptions + "-t %s " % (conf["receiverThr"])
    if (conf["workerThr"]):
        cliOptions = cliOptions + "-w %s " % (conf["workerThr"])

    return cliOptions

def startServerThr(node, cliOptions):
    killer(node, "nsdperfexe")
    #give some time to die
    time.sleep(5)
    chkcmd("ssh %s %s \"%s/nsdperfexe -s %s > %s/server_thread_log 2>&1 &\"" % (sshOption, node, nsdperfPath, cliOptions, nsdperfPath))
    #Give some time to start
    time.sleep(5)

def parseOutput(server, client, output):
    resultFile = open(nsdperfResultFile, 'a')
    pattern = "(\d+)-(\d+) (\w+) ([\d\.]+) MB/sec \(([\d\.]+) msg/sec\), cli (\d+\%) srv (\d+\%), time (\d+), buff (\d+)(.*)([\S\s]*?(network delay times[\S\s]*?msec  nevents\s*(\s*\d+ *\d+\s*)*\s+)+)"
    for match in (re.finditer(pattern, output)):
        result = {"server(s)": server, "client(s)": client}
        result["nServer"] = match.group(1)
        result["nClient"] = match.group(2)
        result["test"] = match.group(3)
        result["throughput(MB/sec)"] = match.group(4)
        result["throughput(msg/sec)"] = match.group(5)
        result["cli%"] = match.group(6)
        result["srv%"] = match.group(7)
        result["testTime"] = match.group(8)
        result["buffsize"] = match.group(9)

        sockThInfo = match.group(10)
        sock = re.search("sock (\d+)", sockThInfo)
        if (sock):
            result["socksize"] = sock.group(1)
        th = re.search("th (\d+)", sockThInfo)
        if (th):
            result["nTesterThread"] = th.group(1)

        result["networkDelay"] = []
        delay = {}
        allDelayInfo = match.group(11)
        oneDelayPattern = ".*?network delay times[\S\s]*?msec  nevents\s*(\s*\d+ *\d+\s*)*"
        for oneDelay in (re.finditer(oneDelayPattern, allDelayInfo)):
            detailedDelayPattern = "(\S+) network delay times \(average ([\d\.]+) msec, median ([\d\.]+) msec, std deviation ([\d\.]+) msec\)\s+msec  nevents\s*((\s*\d+ *\d+\s*)*)"
            detailedDelay = re.search(detailedDelayPattern, oneDelay.group())
            if (detailedDelay):
                delay = {}
                delay["client"] = detailedDelay.group(1)
                delay["average"] = detailedDelay.group(2)
                delay["median"] = detailedDelay.group(3)
                delay["standardDeviation"] = detailedDelay.group(4)
                delay["histogram"] = {}
                allEvents = detailedDelay.group(5)
                eventPattern = "(\d+) +(\d+)"
                for event in (re.finditer(eventPattern, allEvents)):
                    delay["histogram"][event.group(1)] = event.group(2)
                result["networkDelay"].append(delay)
            else:
                halt("Error, cannot match for network delay info")

        outputJson = json.dumps(result)
        resultFile.write(outputJson)
    resultFile.close()

def shortUsage():
    print("Usage: %s [-s|--server server1,server2,... -c|--client client1,client2,...|-n|--nodelist node1,node2,...]" % (os.path.realpath(__file__)))
    print("          [-t|--test test1,test2,...] [-l|--testTime testTimeInSec]")
    print("          [-b|--buffsize buffsizeInByte] [-k|--socksize sockSizeInByte]")
    print("          [-R|--receiverThr nReceiverThread] [-W|--workerThr nWorkerThread] [-T|--testerThr nTesterThread]")
    print("          [-r|--rebuild] [-d|--directory dir] [-h|--help]")

def longUsage():
    print("Usage: %s [-s|--server server1,server2,... -c|--client client1,client2,...] [-n|--nodelist node1,node2,...]" % (os.path.realpath(__file__)))
    print("          [-t|--test test1,test2,...] [-l|--testTime testTimeInSec]")
    print("          [-b|--buffsize buffsizeInByte] [-k|--socksize sockSizeInByte]")
    print("          [-R|--receiverThr nReceiverThread] [-W|--workerThr nWorkerThread] [-T|--testerThr nTesterThread]")
    print("          [-r|--rebuild] [-d|--directory dir] [-h|--help]")
    print("")
    print("This tool is a wrapper over nsdperf.C which helps to automatically build and execute nsdperf tests with given configurations.")
    print("The tool accepts above configuration parameters from command line options as well as configuration file %s." % (nsdperfConfFile))
    print("CLI options will override configuration file when the same parameters are given.")
    print("All needed files and also test results in json format will be put under %s." % (nsdperfPath))
    print("")
    print("Node settings:")
    print("-s|--server server1,server2,...: server node list saparated by comma")
    print("-c|--client client1,client2,...: client node list saparated by comma")
    print("-n|--nodelist node1,node2,...: node list saparated by comma")
    print("Either provide servers and clients or a nodelist.")
    print("When both are provided, the tool will ignore nodelist and use servers and clients for test.")
    print("When using nodelist, the tool will repeat same tests with different node settings:")
    print("1 server -- multiple clients| half servers -- half clients | multiple servers -- 1 client")
    print("")
    print("Test settings:")
    print("-t|--test test1,test2,...: tests saparated by comma")
    print("-l|--testTime testTimeInSec: test time duration in seconds")
    print("Accepted tests: write|read|nwrite|swrite|sread|rw, default is \"read,nwrite\"")
    print("")
    print("Buffer settings:")
    print("-b|--buffsize buffsizeInByte: test buffer size in bytes")
    print("-k|--socksize sockSizeInByte: socket buffer size in bytes")
    print("")
    print("Thread settings:")
    print("-R|--receiverThr nReceiverThread: receiver thread number")
    print("-W|--workerThr nWorkerThread: worker thread number")
    print("-T|--testerThr nTesterThread: tester thread number")
    print("")
    print("Others:")
    print("-r|--rebuild: force rebuild the nsdperf executable before tests")
    print("-d|--directory dir: absolute path of local directory on each node to save nsdperf executable and output files, default is \"/tmp/nsdperf\"")
    print("-h|--help: print this help message")

def log(msg):
    LOG_LOCK.acquire()
    timeStamp = getTimeStamp()
    tid = threading.currentThread().name
    print "%s: %s: %s" % (timeStamp, tid, msg)
    LOG_LOCK.release()

def getTimeStamp():
    return time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())

def halt(msg):
    log('\033[91m' + msg + '\033[0m')
    sys.exit(1)

def chkcmdLiveOutput(cmd):
    cmd = cmd.rstrip()
    log("CMD: %s" % (cmd))
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    lines = []
    rc = p.poll()
    while rc is None:
        line = p.stdout.readline()
        rc = p.poll()
        line = line.rstrip()
        log(line)
        lines.append(line)
    if (rc):
        halt("Error, command failed with rc = %s" % (rc))
    out = '\n'
    return out.join(lines)

def chkcmd(cmd):
    [rc, out, err] = runcmd(cmd)
    out = out.rstrip()
    err = err.rstrip()
    if (rc):
        halt("Error, command <%s> get rc <%s> output <%s> error <%s>" % (cmd, rc, out, err))
    return out

def runcmd(cmd):
    cmd.rstrip()
    log("CMD: %s" % (cmd))
    if (re.search("2>&1", cmd)):
        cmd = cmd + " 2>&1"
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    [out, err] = p.communicate()
    rc = p.returncode
    return [rc, out, err]

def killer(node, string):
    runcmd("ssh %s %s killall %s" % (sshOption, node, string))


# ========== main ==========
# Obtain command line options
conf = {'server': '', 'client': '', 'nodelist': '', 'test': '', 'ttime': '',
        'buffsize': '', 'socksize': '', 'receiverThr': '', 'workerThr': '', 'testerThr': '',
        'rebuild': ''}

try:
    opts, args = getopt.getopt(sys.argv[1:], "hs:c:n:t:l:b:k:R:W:T:rd:",
        ["help", "server=", "client=", "nodelist=", "test=", "testTime=", "buffsize=", "socksize=",
        "nReciverThr=", "nWorkerThr=", "nTesterThr=", "rebuild", "directory="])
except getopt.GetoptError:
    shortUsage()
    sys.exit(1)

for op, value in opts:
    if op in ("-h", "--help"):
        longUsage()
        sys.exit(0)
    elif op in ("-s", "--server"):
        conf["server"] = value.split(",")
    elif op in ("-c", "--client"):
        conf["client"] = value.split(",")
    elif op in ("-n", "--nodelist"):
        conf["nodelist"] = value.split(",")
    elif op in ("-t", "--test"):
        conf["test"] = value.split(",")
    elif op in ("-l", "--testTime"):
        conf["ttime"] = value
    elif op in ("-b", "--buffsize"):
        conf["buffsize"] = value
    elif op in ("-k", "--socksize"):
        conf["socksize"] = value
    elif op in ("-R", "--nReciverThr"):
        conf["receiverThr"] = value
    elif op in ("-W", "--nWorkerThr"):
        conf["workerThr"] = value
    elif op in ("-T", "--nTesterThr"):
        conf["testerThr"] = value
    elif op in ("-r", "--rebuild"):
        conf["rebuild"] = True
    elif op in ("-d", "--directory"):
        nsdperfPath = value
    else:
        log("Error: Unknown option %s" % (op))
        shortUsage()
        sys.exit(1)
# process input arguments and configuration file
processArgs()
nsdperfCmdFile = "%s/nsdperfCmd" % (nsdperfPath)
nsdperfResultFile = "%s/nsdperfResult.json" % (nsdperfPath)
nsdperfexe = "%s/nsdperfexe" % (nsdperfPath)
# create nsdperfexe executable on all nodes if needed
allNodes=[]
if (conf["nodelist"]):
    allNodes.extend(conf["nodelist"])
else:
    allNodes.extend(conf["server"])
    allNodes.extend(conf["client"])
threads = []
for node in allNodes:
    thr = threading.Thread(target = createExecutable, args = (node,))
    thr.start()
    threads.append(thr)
for thr in threads:
    thr.join()
# run test
# delete old result file before test
runcmd("rm -rf %s" % (nsdperfResultFile))
if (conf["nodelist"]):
    nNodes = len(conf["nodelist"])
    if (nNodes <= 1):
        halt("Error: nodelist needs at least 2 nodes (1 server and 1 client), you provided <%s>" % conf["nodelist"])
    elif (nNodes == 2):
        server = [conf["nodelist"][0]]
        client = [conf["nodelist"][1]]
        runTest(server, client)
    elif (nNodes == 3):
        # 1 server, 2 clients
        server = [conf["nodelist"][0]]
        client = conf["nodelist"][1:]
        runTest(server, client)
        # 2 servers, 1 client
        server = conf["nodelist"][0:2]
        client = [conf["nodelist"][2]]
        runTest(server, client)
    else:
        # 1 server, n-1 clients
        server = [conf["nodelist"][0]]
        client = conf["nodelist"][1:]
        runTest(server, client)
        # floor(n/2) servers, (n-floor(n/2)) clients
        splitIndex = math.floor(nNodes/2)
        server = conf["nodelist"][0:splitIndex]
        client = conf["nodelist"][(splitIndex + 1):]
        runTest(server, client)
        # n-1 servers, 1 client
        server = conf["nodelist"][0:-1]
        client = [conf["nodelist"][-1]]
        runTest(server, client)
elif (conf["server"] and conf["client"]):
    runTest(conf["server"], conf["client"])

log("========== All tests completed, congratulations! ==========")
log("========== Test result with json format is in file <%s> ==========" % (nsdperfResultFile))
