#!/usr/bin/python
import json
import os
import sys
import socket
import datetime
import subprocess
import platform
import shlex
import time
import socket
from shutil import copyfile
from decimal import Decimal
import argparse
import operator
from math import sqrt, ceil
from functools import reduce

try:
    raw_input      # Python 2
    PYTHON3 = False
except NameError:  # Python 3
    raw_input = input
    PYTHON3 = True

if PYTHON3:
    import statistics

# Colorful constants
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
NOCOLOR = '\033[0m'

# KPI + runtime acceptance values
MAX_AVG_LATENCY = 1.00  # Acceptance value should be 1 msec or less
FPING_COUNT = 500  # Acceptance value should be 500 or more
PERF_RUNTIME = 1200  # Acceptance value should be 1200 or more
MIN_NSD_THROUGHPUT = 2000  # Acceptance value with lots of margin

# GITHUB URL
GIT_URL = "https://github.com/IBM/SpectrumScale_NETWORK_READINESS"

# devnull redirect destination
DEVNULL = open(os.devnull, 'w')

# This script version, independent from the JSON versions
KOET_VERSION = "1.4"


def load_json(json_file_str):
    # Loads  JSON into a dictionary or quits the program if it cannot. Future
    # might add a try to donwload the JSON if not available before quitting
    try:
        with open(json_file_str, "r") as json_file:
            json_variable = json.load(json_file)
            return json_variable
    except Exception:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "Cannot open JSON file: " + json_file_str)


def json_file_loads(json_file_str):
    #We try to load the JSON and return the success of failure
    try:
        with open(json_file_str, "r") as json_file_test:
            json_variable = json.load(json_file_test)
            json_file_test.close()
            json_loads = True
    except Exception:
        json_loads = False
    return json_loads

def write_json_file_from_dictionary(hosts_dictionary, json_file_str):
    #We are going to generate or overwrite the hosts JSON file
    try:
        with open(json_file_str, "w") as json_file:
            json.dump(hosts_dictionary, json_file)
            print(GREEN + "OK: " + NOCOLOR + "JSON file: " + json_file_str +
                  " [over]written")

    except Exception:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "Cannot write JSON file: " + json_file_str)


def estimate_runtime(hosts_dictionary, fp_count, perf_runtime):
    number_of_hosts = len(hosts_dictionary)
    estimated_rt_fp = number_of_hosts * fp_count
    # use number of hosts + 1 to include N:N iteration of nsdperf
    # add 20 sec per node as startup, shutdown, compile overhead
    estimated_rt_perf = (number_of_hosts + 1) * (20 + perf_runtime)
    estimated_runtime = estimated_rt_fp + estimated_rt_perf
    # minutes we always return 2 even for short test runs
    estimated_runtime_minutes = int(ceil(estimated_runtime / 60.))
    return max(estimated_runtime_minutes, 2)


def parse_arguments():
    parser = argparse.ArgumentParser()
    # We include number of runs and KPI as optional arguments
    parser.add_argument(
        '-l',
        '--latency',
        action='store',
        dest='max_avg_latency',
        help='The KPI latency value as float. ' +
        'The maximum required value for certification is ' +
        str(MAX_AVG_LATENCY) +
        ' msec',
        metavar='KPI_LATENCY',
        type=float,
        default=1.0)
    parser.add_argument(
        '-c',
        '--fping_count',
        action='store',
        dest='fping_count',
        help='The number of fping counts to run per node and test. ' +
        'The value has to be at least 2 seconds.' +
        'The minimum required value for certification is ' +
        str(FPING_COUNT),
        metavar='FPING_COUNT',
        type=int,
        default=500)
    parser.add_argument(
        '--hosts',
        action='store',
        dest='hosts',
        help='IP addreses of hosts on CSV format. ' +
        'Using this overrides the hosts.json file.',
        metavar='HOSTS_CSV',
        type=str,
        default="")
    parser.add_argument(
        '-m',
        '--min_throughput',
        action='store',
        dest='perf_throughput',
        help='The minimum MB/sec required to pass the test. ' +
        'The minimum required value for certification is ' +
        str(MIN_NSD_THROUGHPUT),
        metavar='KPI_THROUGHPUT',
        type=int,
        default=2000)
    parser.add_argument(
        '-p',
        '--perf_runtime',
        action='store',
        dest='perf_runtime',
        help='The seconds of nsdperf runtime per test. ' +
        'The value has to be at least 10 seconds.' +
        'The minimum required value for certification is ' +
        str(PERF_RUNTIME),
        metavar='PERF_RUNTIME',
        type=int,
        default=1200)

    parser.add_argument(
        '--save-hosts',
        action='store_true',
        dest='save_hosts',
        help='[over]writes hosts.json with the hosts passed with ' +
        '--hosts. It does not prompt for confirmation when overwriting',
        default=False)

    parser.add_argument('-v', '--version', action='version',
                        version='KOET ' + KOET_VERSION)
    args = parser.parse_args()
    if args.max_avg_latency <= 0:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "KPI latency cannot be zero or negative number\n")
    if args.fping_count <= 1:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "fping count cannot be less than 2\n")
    if args.perf_throughput <= 0:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "KPI throughput cannot be zero or negative number\n")
    if args.perf_runtime <= 9:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "nsdperf runtime cannot be less than 10 seconds\n")
    # we check is a CSV string and if so we put it on dictionary
    cli_hosts = False
    hosts_dictionary = {}
    if args.hosts != "":
        cli_hosts = True
        try:
            host_raw = args.hosts
            hosts = host_raw.split(",")
            for host_key in hosts:
                hosts_dictionary.update({host_key: "ECE"})
        except Exception:
            sys.exit(RED + "QUIT: " + NOCOLOR +
                     "hosts parameter is not on CSV format")

    if args.save_hosts and not cli_hosts:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "cannot generate hosts file if hosts not passed with --hosts")

    return (round(args.max_avg_latency, 2), args.fping_count,
            args.perf_runtime, args.perf_throughput,
            cli_hosts, hosts_dictionary, args.save_hosts)


def check_kpi_is_ok(max_avg_latency, fping_count, perf_bw, perf_rt):
    if max_avg_latency > MAX_AVG_LATENCY:
        latency_kpi_certifies = False
    else:
        latency_kpi_certifies = True

    if fping_count < FPING_COUNT:
        fping_count_certifies = False
    else:
        fping_count_certifies = True

    if perf_bw < MIN_NSD_THROUGHPUT:
        perf_bw_certifies = False
    else:
        perf_bw_certifies = True

    if perf_rt < PERF_RUNTIME:
        perf_rt_certifies = False
    else:
        perf_rt_certifies = True

    return (latency_kpi_certifies, fping_count_certifies, perf_bw_certifies,
            perf_rt_certifies)


def show_header(koet_h_version, json_version,
                estimated_runtime_str, max_avg_latency,
                fping_count, perf_throughput, perf_runtime):
    # Say hello and give chance to disagree
    while True:
        print("")
        print(GREEN + "Welcome to KOET, version " + koet_h_version + NOCOLOR)
        print("")
        print("JSON files versions:")
        print("\tsupported OS:\t\t" + json_version['supported_OS'])
        print("\tpackages: \t\t" + json_version['packages'])
        print("")
        print("Please use " + GIT_URL +
              " to get latest versions and report issues about this tool.")
        print("")
        print(
            "The purpose of KOET is to obtain IPv4 network metrics " +
            "for a number of nodes.")
        print("")
        lat_kpi_ok, fping_kpi_ok, perf_kpi_ok, perf_rt_ok = check_kpi_is_ok(
            max_avg_latency, fping_count, perf_throughput, perf_runtime)
        if lat_kpi_ok:
            print(GREEN + "The latency KPI value of " + str(max_avg_latency) +
                  " msec is good to certify the environment" + NOCOLOR)
        else:
            print(
                YELLOW +
                "WARNING: " +
                NOCOLOR +
                "The latency KPI value of " +
                str(max_avg_latency) +
                " msec is too high to certify the environment")
        print("")
        if fping_kpi_ok:
            print(
                GREEN +
                "The fping count value of " +
                str(fping_count) +
                " ping per test and node is good to certify the " +
                "environment" + NOCOLOR)
        else:
            print(
                YELLOW +
                "WARNING: " +
                NOCOLOR +
                "The fping count value of " +
                str(fping_count) +
                " ping per test and node is not enough " +
                "to certify the environment")
        print("")
        if perf_kpi_ok:
            print(
                GREEN +
                "The throughput value of " +
                str(perf_throughput) +
                " MB/sec is good to certify the environment" +
                NOCOLOR)
        else:
            print(
                YELLOW +
                "WARNING: " +
                NOCOLOR +
                "The throughput value of " +
                str(perf_throughput) +
                " MB/sec is not enough to certify the environment")
        print("")
        if perf_rt_ok:
            print(
                GREEN +
                "The performance runtime value of " +
                str(perf_runtime) +
                " second per test and node is good to certify the " +
                "environment" + NOCOLOR)
        else:
            print(
                YELLOW +
                "WARNING: " +
                NOCOLOR +
                "The performance runtime value of " +
                str(perf_runtime) +
                " second per test and node is not enough " +
                "to certify the environment")
        print("")
        print(
            YELLOW +
            "It requires remote ssh passwordless between all nodes for user " +
            "root already configured" +
            NOCOLOR)
        print("")
        print(YELLOW + "This test run estimation is " +
              estimated_runtime_str + " minutes" + NOCOLOR)
        print("")
        print(
            RED +
            "This software comes with absolutely no warranty of any kind. " +
            "Use it at your own risk" +
            NOCOLOR)
        print("")
        print(
            RED +
            "NOTE: The bandwidth numbers shown in this tool are for a very " +
            "specific test. This is not a storage benchmark." +
            NOCOLOR)
        print(
            RED +
            "They do not necessarily reflect the numbers you would see with " +
            "Spectrum Scale and your particular workload" +
            NOCOLOR)
        print("")
        run_this = raw_input("Do you want to continue? (y/n): ")
        if run_this.lower() == 'y':
            break
        if run_this.lower() == 'n':
            print
            sys.exit("Have a nice day! Bye.\n")
    print("")


def check_os_redhat(os_dictionary):
    # Check redhat-release vs dictionary list
    redhat_distribution = platform.linux_distribution()
    redhat_distribution_str = redhat_distribution[0] + \
        " " + redhat_distribution[1]
    error_message = RED + "QUIT: " + NOCOLOR + " " + \
        redhat_distribution_str + " is not a supported OS for this tool\n"
    try:
        if os_dictionary[redhat_distribution_str] == 'OK':
            print(GREEN + "OK: " + NOCOLOR + redhat_distribution_str +
                  " is a supported OS for this tool")
            print
        else:
            sys.exit(error_message)
            print
    except Exception:
        sys.exit(error_message)
        print("")


def get_json_versions(os_dictionary, packages_dictionary):
    # Gets the versions of the json files into a dictionary
    json_version = {}

    # Lets see if we can load version, if not quit
    try:
        json_version['supported_OS'] = os_dictionary['json_version']
    except Exception:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "Cannot load version from supported OS JSON")
    try:
        json_version['packages'] = packages_dictionary['json_version']
    except Exception:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "Cannot load version from packages JSON")

    # If we made it this far lets return the dictionary. This was being stored
    # in its own file before
    return json_version


def check_distribution():
    # Decide if this is a redhat or a CentOS. We only checking the running
    # node, that might be a problem
    what_dist = platform.dist()[0]
    if what_dist == "redhat" or "centos":
        return what_dist
    else:  # everything esle we fail
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "this only runs on RedHat at this moment")


def ssh_rpm_is_installed(host, rpm_package):
    # returns the RC of rpm -q rpm_package or quits if it cannot run rpm
    errors = 0
    try:
        return_code = subprocess.call(['ssh',
                                       '-o',
                                       'StrictHostKeyChecking=no',
                                       host,
                                       'rpm',
                                       '-q',
                                       rpm_package],
                                      stdout=DEVNULL,
                                      stderr=DEVNULL)
    except Exception:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "cannot run rpm over ssh on host " + host)
    return return_code


def check_tcp_port_free(hosts_dictionary, tcpport):
    errors = 0
    # Checks certain port is not in use
    for host in hosts_dictionary.keys():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        openit = sock.connect_ex((host, tcpport))
        if openit == 0:  # I can connect so it is NOT free
            errors = errors + 1
            print(RED +
                  "ERROR: " +
                  NOCOLOR +
                  "on host " +
                  str(host) +
                  " TCP port " +
                  str(tcpport) +
                  " seems to be not free")
        else:  # cannot connect so not in used or not accesible
            print(
                GREEN +
                "OK: " +
                NOCOLOR +
                "on host " +
                str(host) +
                " TCP port " +
                str(tcpport) +
                " seems to be free")

    if errors > 0:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "TCP port " + str(tcpport) + " is not free in all hosts")


def host_packages_check(hosts_dictionary, packages_dictionary):
    # Checks if packages from JSON are installed or not based on the input
    # data ont eh JSON
    errors = 0
    print("Checking packages install status:")
    print("")
    for host in hosts_dictionary.keys():
        for rpm_package in packages_dictionary.keys():
            if rpm_package != "json_version":
                current_package_rc = ssh_rpm_is_installed(host, rpm_package)
                expected_package_rc = packages_dictionary[rpm_package]
                if current_package_rc == expected_package_rc:
                    print(
                        GREEN +
                        "OK: " +
                        NOCOLOR +
                        "on host " +
                        host +
                        " the " +
                        rpm_package +
                        " installation status is as expected")
                else:
                    print(
                        RED +
                        "ERROR: " +
                        NOCOLOR +
                        "on host " +
                        host +
                        " the " +
                        rpm_package +
                        " installation status is *NOT* as expected")
                    errors = errors + 1
    if errors > 0:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "Fix the packages before running this tool again.\n")


def is_IP_address(ip):
    # Lets check is a full ip by counting dots
    if ip.count('.') != 3:
        return False
    try:
        socket.inet_aton(ip)
        return True
    except Exception:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "cannot check IP address " + ip + "\n")


def check_hosts_are_ips(hosts_dictionary):
    for host in hosts_dictionary.keys():
        is_IP = is_IP_address(host)
        if not is_IP:
            sys.exit(
                RED +
                "QUIT: " +
                NOCOLOR +
                "on hosts JSON file or CLI parameter '" +
                host +
                "' is not a valid IPv4. Fix before running this tool again.\n")


def check_hosts_number(hosts_dictionary):
    number_unique_hosts = len(hosts_dictionary)
    number_unique_hosts_str = str(number_unique_hosts)
    if len(hosts_dictionary) > 32 or len(hosts_dictionary) < 4:
        sys.exit(
            RED +
            "QUIT: " +
            NOCOLOR +
            "the number of hosts is not valid. It is " +
            number_unique_hosts_str +
            " and should be between 4 and 32 unique hosts.\n")


def create_log_dir():
    # datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    logdir = os.path.join(
        os.getcwd(),
        'log',
        datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
    try:
        os.makedirs(logdir)
        return logdir
    except Exception:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "cannot create directory " + logdir + "\n")


def latency_test(hosts_dictionary, logdir, fping_count):
    fping_count_str = str(fping_count)
    hosts_fping = ""
    for host in hosts_dictionary.keys():  # we ping ourselvels as well
        hosts_fping = hosts_fping + host + " "

    for srchost in hosts_dictionary.keys():
        print("")
        print("Starting ping run from " + srchost + " to all nodes")
        fileurl = os.path.join(logdir, "lat_" + srchost + "_" + "all")
        command = "ssh -o StrictHostKeyChecking=no " + srchost + \
            " fping -C " + fping_count_str + " -q -A " + hosts_fping
        with open(fileurl, 'wb', 0) as logfping:
            runfping = subprocess.Popen(shlex.split(
                command), stderr=subprocess.STDOUT, stdout=logfping)
            runfping.wait()
            logfping.close()
        print("Ping run from " + srchost + " to all nodes completed")


def throughput_test_os(command, nsd_logfile, client):
    try:
        runperf = subprocess.Popen(shlex.split(command), stdout=nsd_logfile)
        runperf.wait()
        # Extra wait here it might be not needed now that we added it on
        # nsdperTool.py startup, but we keep it.
        time.sleep(5)
    except BaseException:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "Throughput run " + client + " failed unexpectedly\n")


def throughput_test(hosts_dictionary, logdir, perf_runtime):
    throughput_json_files_list = []
    print("")
    print("Starting throughput tests. Please be patient.")
    for client in hosts_dictionary.keys():
        print("")
        print("Starting throughput run from " + client + " to all nodes")
        server_hosts_dictionary = dict(hosts_dictionary)
        del server_hosts_dictionary[client]
        server_csv_str = (",".join(server_hosts_dictionary.keys()))
        # Craft the call of nsdperf exec/wrapper
        command = "./nsdperfTool.py -t read -k 4194304 -b 4194304 " \
            "-R 256 -W 256 -T 256 -d " + logdir + " -s " + \
            server_csv_str + " -c " + client + " -l " + str(perf_runtime)
        nsd_logfile = open(logdir + "/nsdperfTool_log", "a")
        throughput_test_os(command, nsd_logfile, client)
        nsd_logfile.close()
        # Copy the file to avoid overwrite it
        copyfile(logdir + "/nsdperfResult.json", logdir + "/nsd_" +
                 client + ".json")
        print("Completed throughput run from " + client + " to all nodes")
    print("")
    print("Starting many to many nodes throughput test")
    # We run a mess run to catch few more issues
    middle_index = int(len(hosts_dictionary)/2)
    if PYTHON3:
        clients_nodes_d = dict(list(hosts_dictionary.items())[middle_index:])
        servers_nodes_d = dict(list(hosts_dictionary.items())[:middle_index])
    else:
        clients_nodes_d = dict(hosts_dictionary.items()[middle_index:])
        servers_nodes_d = dict(hosts_dictionary.items()[:middle_index])
    clients_csv = (",".join(clients_nodes_d.keys()))
    servers_csv = (",".join(servers_nodes_d.keys()))
    command = "./nsdperfTool.py -t read -k 4194304 -b 4194304 " \
        "-R 256 -W 256 -T 256 -d " + logdir + " -s " + \
        servers_csv + " -c " + clients_csv + " -l " + str(perf_runtime)
    nsd_logfile = open(logdir + "/nsdperfTool_log", "a")
    throughput_test_os(command, nsd_logfile, client)
    nsd_logfile.close()
    # Copy the file to avoid overwrite it
    copyfile(logdir + "/nsdperfResult.json", logdir + "/nsd_mess" + ".json")
    print("Completed Many to many nodes throughput test")
    return clients_nodes_d


def mean_list(list):
    if len(list) == 0:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "cannot calculate mean of list: " + repr(list) + "\n")
    # We replace a timeout "-" for 1 sec latency
    list = [lat.replace('-', '1000.00') for lat in list]
    list = [float(lat) for lat in list]  # we convert them to float
    mean = sum(list) / len(list)
    return mean


def max_list(list):
    if len(list) == 0:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "cannot calculate max of list: " + repr(list) + "\n")
    # We replace a timeout "-" for 1 sec latency
    list = [lat.replace('-', '1000.00') for lat in list]
    list = [float(lat) for lat in list]
    max_lat = max(list)
    return max_lat


def min_list(list):
    if len(list) == 0:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "cannot calculate min of list: " + repr(list) + "\n")
    # We replace a timeout "-" for 1 sec latency
    list = [lat.replace('-', '1000.00') for lat in list]
    list = [float(lat) for lat in list]
    min_lat = min(list)
    return min_lat


def stddev_list(list, mean):
    if len(list) == 0:
        sys.exit(
            RED +
            "QUIT: " +
            NOCOLOR +
            "cannot calculate standard deviation of list: " +
            repr(list) +
            "\n")
    # We replace a timeout "-" for 1 sec latency
    list = [lat.replace('-', '1000.00') for lat in list]
    list = [float(lat) for lat in list]
    if PYTHON3:
        stddev_lat = statistics.stdev(list)
    else:
        stddev_lat = sqrt(float(
            reduce(lambda x, y: x + y, map(
                lambda x: (x - mean) ** 2, list))) / len(list))
    stddev_lat = Decimal(stddev_lat)
    stddev_lat = round(stddev_lat, 2)
    return stddev_lat


def pct_diff_list(bw_str_list):
    # as the rest expects a str
    try:
        pc_diff_bw = abs(float(min(bw_str_list)) * 100 /
                         float(max(bw_str_list)))
    except BaseException:
        sys.exit(
            RED +
            "QUIT: " +
            NOCOLOR +
            "cannot calculate mean of bandwidth run")
    return pc_diff_bw


def file_exists(fileurl):
    # Lets check the files do actually exists
    if os.path.isfile(fileurl):
        pass
    else:
        sys.exit(RED + "QUIT: " + NOCOLOR + " cannot find file: " +
                 fileurl)


def load_json_files_into_dictionary(json_files_list):
    all_json_dict = {}
    try:
        for json_file in json_files_list:
            json_file_name = open(json_file, 'r')
            all_json_dict[json_file] = json.load(json_file_name)
        return all_json_dict
    except BaseException:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 " cannot load JSON file: " + json_file)


def load_throughput_tests(logdir, hosts_dictionary, many2many_clients):
    throughput_dict = {}
    nsd_lat_dict = {}
    nsd_std_dict = {}
    nsd_rxe_dict = {}
    nsd_rxe_m2m_d = {}
    nsd_txe_dict = {}
    nsd_txe_m2m_d = {}
    nsd_rtr_dict = {}
    nsd_rtr_m2m_d = {}
    file_host_dict = {}
    throughput_json_files_list = []
    for host in hosts_dictionary.keys():
        fileurl = logdir + "/nsd_" + host + ".json"
        file_exists(fileurl)
        #Lets do a load to check it is a proper file
        json_loads = json_file_loads(fileurl)
        if json_loads:
            throughput_json_files_list.append(fileurl)
            file_host_dict.update({fileurl: host})
        else:
            print(RED +
                  "ERROR: " +
                  NOCOLOR +
                  "cannot load JSON for host " +
                  host +
                  ". We are going to ignore this host on the results")
    # We append the mess run
    mess_file_url = logdir + "/nsd_mess.json"
    #Lets do a load to check it is a proper file
    json_loads = json_file_loads(mess_file_url)
    if json_loads:
            throughput_json_files_list.append(mess_file_url)
            file_host_dict.update({mess_file_url: "all at the same time"})
    else:
        print(RED +
              "ERROR: " +
              NOCOLOR +
              "cannot load JSON for all at the same time " +
              ". We are going to ignore this test on the results")
    # If the list is empty is that failed to load all JSON, no point to go
    if len(throughput_json_files_list) == 0:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 " cannot load any throughput JSON file")
    nsd_json = load_json_files_into_dictionary(throughput_json_files_list)
    for file in throughput_json_files_list:
        # here we add the metrics we will proces later
        host_key = file_host_dict[file]
        throughput_v = Decimal(nsd_json[file]['throughput(MB/sec)'])
        throughput_dict.update({host_key: throughput_v})
        n_lt_v = Decimal(nsd_json[file]['networkDelay'][0]['average'])
        nsd_lat_dict.update({host_key: n_lt_v})
        n_std = Decimal(nsd_json[file]['networkDelay'][0]['standardDeviation'])
        nsd_std_dict.update({host_key: n_std})
        if host_key == "all at the same time":
            for host in many2many_clients.keys():
                n_rxe = Decimal(nsd_json[file]['netData'][host]['rxErrors'])
                nsd_rxe_m2m_d.update({host: n_rxe})
                n_txe = Decimal(nsd_json[file]['netData'][host]['txErrors'])
                nsd_txe_m2m_d.update({host: n_txe})
                n_rtr = Decimal(nsd_json[file]['netData'][host]['retransmit'])
                nsd_rtr_m2m_d.update({host: n_rtr})
        else:
            n_rxe = Decimal(nsd_json[file]['netData'][host_key]['rxErrors'])
            nsd_rxe_dict.update({host_key: n_rxe})
            n_txe = Decimal(nsd_json[file]['netData'][host_key]['txErrors'])
            nsd_txe_dict.update({host_key: n_txe})
            n_rtr = Decimal(nsd_json[file]['netData'][host_key]['retransmit'])
            nsd_rtr_dict.update({host_key: n_rtr})

    # lets calculate % diff max min mean etc ...
    bw_str_list = []
    # filter "all" out of list of node bandwidths
    bw_str_list = [str(throughput_dict[k]) for k in throughput_dict
                   if k != 'all at the same time']
    pc_diff_bw = pct_diff_list(bw_str_list)
    max_bw = max_list(bw_str_list)
    min_bw = min_list(bw_str_list)
    mean_bw = mean_list(bw_str_list)
    stddev_bw = stddev_list(bw_str_list, mean_bw)
    pc_diff_bw = round(pc_diff_bw, 2)
    mean_bw = round(mean_bw, 2)
    return (throughput_dict, nsd_lat_dict, nsd_std_dict, pc_diff_bw, max_bw,
            min_bw, mean_bw, stddev_bw, nsd_rxe_dict, nsd_rxe_m2m_d,
            nsd_txe_dict, nsd_txe_m2m_d, nsd_rtr_dict, nsd_rtr_m2m_d)


def load_multiple_fping(logdir, hosts_dictionary):
    all_fping_dictionary = {}
    all_fping_dictionary_max = {}
    all_fping_dictionary_min = {}
    all_fping_dictionary_stddev = {}
    mean_all = []
    max_all = []
    min_all = []
    # Loads log file and returns dictionary
    for srchost in hosts_dictionary.keys():
        fileurl = os.path.join(logdir, "lat_" + srchost + "_all")
        file_exists(fileurl)
        logfping = open(fileurl, 'r')
        for rawfping in logfping:
            hostIP = rawfping.split(':')[0]
            hostIP = hostIP.rstrip(' ')
            if srchost == hostIP:  # we ignore ourselves
                continue
            latencies = rawfping.split(':')[1]
            latencies = latencies.lstrip(' ')  # Clean up first space
            latencies = latencies.rstrip('\n')  # Clean up new line character
            latencies_list = latencies.split(' ')
            # our mean calculation expect strings. Need to change this when
            # optimizing
            mean_all.append(str(mean_list(latencies_list)))
            max_all.append(max(latencies_list))
            min_all.append(min(latencies_list))
        # we use Decimal to round the results
        mean = Decimal(mean_list(mean_all))
        mean = round(mean, 2)  # we round to 2 decimals
        all_fping_dictionary[srchost] = mean
        all_fping_dictionary_max[srchost] = max_list(max_all)
        all_fping_dictionary_min[srchost] = min_list(min_all)
        all_fping_dictionary_stddev[srchost] = stddev_list(mean_all, mean)
        mean_all = []
        max_all = []
        min_all = []
    return (all_fping_dictionary, all_fping_dictionary_max,
            all_fping_dictionary_min, all_fping_dictionary_stddev)


def nsd_KPI(min_nsd_throughput,
            throughput_dict,
            nsd_lat_dict,
            nsd_std_dict,
            pc_diff_bw,
            max_bw,
            min_bw,
            mean_bw,
            stddev_bw,
            nsd_rxe_dict,
            nsd_rxe_m2m_d,
            nsd_txe_dict,
            nsd_txe_m2m_d,
            nsd_rtr_dict,
            nsd_rtr_m2m_d):
    errors = 0
    print("Results for throughput test ")
    for host in throughput_dict.keys():
        if throughput_dict[host] < min_nsd_throughput:
            errors = errors + 1
            print(RED +
                  "ERROR: " +
                  NOCOLOR +
                  "on host " +
                  host +
                  " the throughput test result is " +
                  str(throughput_dict[host]) +
                  " MB/sec. Which is less than the KPI of " +
                  str(min_nsd_throughput) +
                  " MB/sec")
        else:
            print(GREEN +
                  "OK: " +
                  NOCOLOR +
                  "on host " +
                  host +
                  " the throughput test result is " +
                  str(throughput_dict[host]) +
                  " MB/sec. Which is higher than the KPI of " +
                  str(min_nsd_throughput) +
                  " MB/sec")

    if pc_diff_bw < 79:
        errors = errors + 1
        print(RED +
              "ERROR: " +
              NOCOLOR +
              "the difference of throughput between maximum and minimum " +
              "values is " + str(abs(100 - pc_diff_bw)) + "%, which is more " +
              "than 20% defined on the KPI")
    else:
        print(GREEN +
              "OK: " +
              NOCOLOR +
              "the difference of throughput between maximum and minimum " +
              "values is " + str(abs(100 - pc_diff_bw)) + "%, which is less " +
              "than 20% defined on the KPI")

    print("")
    print("The following metrics are not part of the KPI and " +
           "are shown for informational purposes only")
    print(GREEN +
          "INFO: " +
          NOCOLOR +
          "The maximum throughput value is " + str(max_bw))
    print(GREEN +
          "INFO: " +
          NOCOLOR +
          "The minimum throughput value is " + str(min_bw))
    print(GREEN +
          "INFO: " +
          NOCOLOR +
          "The mean throughput value is " + str(mean_bw))
    print(GREEN +
          "INFO: " +
          NOCOLOR +
          "The standard deviation throughput value is " + str(stddev_bw))
    for host in nsd_lat_dict.keys():
        print(GREEN +
              "INFO: " +
              NOCOLOR +
              "The average NSD latency for " +
              str(host) +
              " is " +
              str(nsd_lat_dict[host]) +
              " msec")
    for host in nsd_std_dict.keys():
        print(GREEN +
              "INFO: " +
              NOCOLOR +
              "The standard deviation of NSD latency for " +
              str(host) +
              " is " +
              str(nsd_std_dict[host]) +
              " msec")
    for host in nsd_rxe_dict.keys():
        print(GREEN +
              "INFO: " +
              NOCOLOR +
              "The packet Rx error count for throughput test on " +
              str(host) +
              " is equal to " +
              str(nsd_rxe_dict[host]) +
              " packet[s]")
    for host in nsd_txe_dict.keys():
        print(GREEN +
              "INFO: " +
              NOCOLOR +
              "The packet Tx error count for throughput test on " +
              str(host) +
              " is equal to " +
              str(nsd_txe_dict[host]) +
              " packet[s]")
    for host in nsd_rtr_dict.keys():
        print(GREEN +
              "INFO: " +
              NOCOLOR +
              "The packet retransmit count for throughput test on " +
              str(host) +
              " is equal to " +
              str(nsd_rtr_dict[host]) +
              " packet[s]")
    packets_rxe = 0
    for host in nsd_rxe_m2m_d.keys():
        packets_rxe = packets_rxe + nsd_rxe_m2m_d[host]
    print(GREEN +
          "INFO: " +
          NOCOLOR +
          "The packet Rx error count for throughput test on many to many" +
          " is equal to " +
          str(packets_rxe) +
          " packet[s]")
    packets_txe = 0
    for host in nsd_txe_m2m_d.keys():
        packets_txe = packets_txe + nsd_txe_m2m_d[host]
    print(GREEN +
          "INFO: " +
          NOCOLOR +
          "The packet Tx error count for throughput test on many to many" +
          " is equal to " +
          str(packets_txe) +
          " packet[s]")
    packets_rtr = 0
    for host in nsd_rtr_m2m_d.keys():
        packets_rtr = packets_rtr + nsd_rtr_m2m_d[host]
    print(GREEN +
          "INFO: " +
          NOCOLOR +
          "The packet retransmit count for throughput test many to many" +
          " is equal to " +
          str(packets_rtr) +
          " packet[s]")
    return errors


def fping_KPI(
        fping_dictionary,
        fping_dictionary_max,
        fping_dictionary_min,
        fping_dictionary_stddev,
        test_string,
        max_avg_latency,
        max_max_latency,
        max_stddev_latency):
    errors = 0

    print("Results for ICMP latency test " + test_string + "")
    max_avg_latency_str = str(round(max_avg_latency, 2))
    max_max_latency_str = str(round(max_max_latency, 2))
    max_stddev_latency_str = str(round(max_stddev_latency, 2))
    for host in fping_dictionary.keys():
        if fping_dictionary[host] >= max_avg_latency:
            errors = errors + 1  # yes yes +=
            print(RED +
                  "ERROR: " +
                  NOCOLOR +
                  "on host " +
                  host +
                  " the " +
                  test_string +
                  " average ICMP latency is " +
                  str(fping_dictionary[host]) +
                  " msec. Which is higher than the KPI of " +
                  max_avg_latency_str +
                  " msec")
        else:
            print(GREEN +
                  "OK: " +
                  NOCOLOR +
                  "on host " +
                  host +
                  " the " +
                  test_string +
                  " average ICMP latency is " +
                  str(fping_dictionary[host]) +
                  " msec. Which is lower than the KPI of " +
                  max_avg_latency_str +
                  " msec")

        if fping_dictionary_max[host] >= max_max_latency:
            errors = errors + 1
            print(RED +
                  "ERROR: " +
                  NOCOLOR +
                  "on host " +
                  host +
                  " the " +
                  test_string +
                  " maximum ICMP latency is " +
                  str(fping_dictionary_max[host]) +
                  " msec. Which is higher than the KPI of " +
                  max_max_latency_str +
                  " msec")
        else:
            print(GREEN +
                  "OK: " +
                  NOCOLOR +
                  "on host " +
                  host +
                  " the " +
                  test_string +
                  " maximum ICMP latency is " +
                  str(fping_dictionary_max[host]) +
                  " msec. Which is lower than the KPI of " +
                  max_max_latency_str +
                  " msec")

        if fping_dictionary_min[host] >= max_avg_latency:
            errors = errors + 1
            print(RED +
                  "ERROR: " +
                  NOCOLOR +
                  "on host " +
                  host +
                  " the " +
                  test_string +
                  " minimum ICMP latency is " +
                  str(fping_dictionary_min[host]) +
                  " msec. Which is higher than the KPI of " +
                  max_avg_latency_str +
                  " msec")
        else:
            print(GREEN +
                  "OK: " +
                  NOCOLOR +
                  "on host " +
                  host +
                  " the " +
                  test_string +
                  " minimum ICMP latency is " +
                  str(fping_dictionary_min[host]) +
                  " msec. Which is lower than the KPI of " +
                  max_avg_latency_str +
                  " msec")

        if fping_dictionary_stddev[host] >= max_stddev_latency:
            errors = errors + 1
            print(RED +
                  "ERROR: " +
                  NOCOLOR +
                  "on host " +
                  host +
                  " the " +
                  test_string +
                  " standard deviation of ICMP latency is " +
                  str(fping_dictionary_stddev[host]) +
                  " msec. Which is higher than the KPI of " +
                  max_stddev_latency_str +
                  " msec")
        else:
            print(GREEN +
                  "OK: " +
                  NOCOLOR +
                  "on host " +
                  host +
                  " the " +
                  test_string +
                  " standard deviation of ICMP latency is " +
                  str(fping_dictionary_stddev[host]) +
                  " msec. Which is lower than the KPI of " +
                  max_stddev_latency_str +
                  " msec")
        print("")

    return errors  # Use this to give number of nodes is not exact in all cases


def test_ssh(hosts_dictionary):
    for host in hosts_dictionary.keys():
        try:
            ssh_return_code = subprocess.call(['ssh',
                                               '-oStrictHostKeyChecking=no',
                                               '-oBatchMode=yes',
                                               '-o ConnectTimeout=5',
                                               host,
                                               'uname'],
                                              stdout=DEVNULL,
                                              stderr=DEVNULL)
            if ssh_return_code == 0:
                print(GREEN + "OK: " + NOCOLOR +
                      "SSH with node " + host + " works")
            else:
                sys.exit(
                    RED +
                    "QUIT: " +
                    NOCOLOR +
                    "cannot run ssh to " +
                    host +
                    ". Please fix this problem before running this tool again")
        except Exception:
            sys.exit(
                RED +
                "QUIT: " +
                NOCOLOR +
                "cannot run ssh to " +
                host +
                ". Please fix this problem before running this tool again")
    print("")


def print_end_summary(a_avg_fp_err, a_nsd_err, lat_kpi_ok,
                      fping_kpi_ok, perf_kpi_ok, perf_rt_ok):
    # End summary and say goodbye
    passed = True
    print("")
    print("The summary of this run:")
    print("")

    if a_avg_fp_err > 0:
        print(RED + "\tThe 1:n ICMP latency test failed " +
              str(a_avg_fp_err) + " time[s]" + NOCOLOR)
        passed = False
    else:
        print(
            GREEN +
            "\tThe 1:n ICMP average latency was successful in all nodes" +
            NOCOLOR)

    if a_nsd_err > 0:
        print(RED + "\tThe 1:n throughput test failed " +
              str(a_nsd_err) + " time[s]" + NOCOLOR)
        passed = False
    else:
        print(
            GREEN +
            "\tThe 1:n throughput test was successful in all nodes" +
            NOCOLOR)
    print("")

    if passed:
        print(
            GREEN +
            "OK: " +
            NOCOLOR +
            "All tests had been passed" +
            NOCOLOR)
    else:
        print(
            RED +
            "ERROR: " +
            NOCOLOR +
            "All test must be passed to certify the environment " +
            "to proceed with the next steps" +
            NOCOLOR)

    if lat_kpi_ok and fping_kpi_ok and perf_kpi_ok and perf_kpi_ok \
       and perf_rt_ok and passed:
        print(
            GREEN +
            "OK: " +
            NOCOLOR +
            "You can proceed with the next steps" +
            NOCOLOR)
        valid_test = 0
    else:
        print(
            RED +
            "ERROR: " +
            NOCOLOR +
            "This run is not valid to certify the environment. " +
            "You cannot proceed with the next steps" +
            NOCOLOR)
        valid_test = 5
    print("")
    return (a_avg_fp_err + a_nsd_err + valid_test)


def main():
    # Parsing input
    max_avg_latency, fping_count, perf_runtime, min_nsd_throughput, \
         cli_hosts, hosts_dictionary, save_hosts = parse_arguments()
    max_max_latency = max_avg_latency * 2
    max_stddev_latency = max_avg_latency / 3

    # JSON loads
    os_dictionary = load_json("supported_OS.json")
    packages_dictionary = load_json("packages.json")
    if not cli_hosts:
        hosts_dictionary = load_json("hosts.json")

    # Check hosts are IP addresses
    check_hosts_are_ips(hosts_dictionary)

    # Check hosts are 4 to 32
    check_hosts_number(hosts_dictionary)

    # Initial header
    json_version = get_json_versions(os_dictionary, packages_dictionary)
    estimated_runtime_str = str(
        estimate_runtime(hosts_dictionary, fping_count, perf_runtime))
    show_header(KOET_VERSION, json_version, estimated_runtime_str,
                max_avg_latency, fping_count, min_nsd_throughput, perf_runtime)

    #JSON hosts write
    if save_hosts:
        write_json_file_from_dictionary(hosts_dictionary, "hosts.json")

    # Checks
    # Check OS
    linux_distribution = check_distribution()

    if linux_distribution == "redhat" or "centos":
        check_os_redhat(os_dictionary)
    else:
        sys.exit(RED + "QUIT: " + NOCOLOR +
                 "this is not a supported Linux distribution for this tool\n")

    # Check SSH
    test_ssh(hosts_dictionary)

    # Check packages are installed
    host_packages_check(hosts_dictionary, packages_dictionary)

    # Check TCP port 6668 is not in use. Limited from view of this host
    check_tcp_port_free(hosts_dictionary, 6668)

    # Run
    logdir = create_log_dir()
    latency_test(hosts_dictionary, logdir, fping_count)
    many2many_clients = throughput_test(hosts_dictionary,
                                        logdir, perf_runtime)

    # Load results
    all_fping_dictionary, all_fping_dictionary_max, all_fping_dictionary_min, \
        all_fping_dictionary_stddev = load_multiple_fping(logdir,
                                                          hosts_dictionary)
    throughput_dict, nsd_lat_dict, nsd_std_dict, pc_diff_bw, max_bw, min_bw, \
        mean_bw, stddev_bw, nsd_rxe_dict, nsd_rxe_m2m_d, nsd_txe_dict, \
        nsd_txe_m2m_d, nsd_rtr_dict, nsd_rtr_m2m_d = load_throughput_tests(
                                                        logdir,
                                                        hosts_dictionary,
                                                        many2many_clients)

    # Compare againsts KPIs
    print("")
    all_avg_fping_errors = fping_KPI(
        all_fping_dictionary,
        all_fping_dictionary_max,
        all_fping_dictionary_min,
        all_fping_dictionary_stddev,
        "1:n",
        max_avg_latency,
        max_max_latency,
        max_stddev_latency)
    all_nsd_errors = nsd_KPI(min_nsd_throughput, throughput_dict, nsd_lat_dict,
                             nsd_std_dict, pc_diff_bw, max_bw, min_bw,
                             mean_bw, stddev_bw, nsd_rxe_dict, nsd_rxe_m2m_d,
                             nsd_txe_dict, nsd_txe_m2m_d, nsd_rtr_dict,
                             nsd_rtr_m2m_d)

    # Exit protocol
    lat_kpi_ok, fping_kpi_ok, perf_kpi_ok, perf_rt_ok = check_kpi_is_ok(
        max_avg_latency, fping_count, min_nsd_throughput, perf_runtime)
    DEVNULL.close()
    return_code = print_end_summary(
        all_avg_fping_errors,
        all_nsd_errors,
        lat_kpi_ok,
        fping_kpi_ok,
        perf_kpi_ok,
        perf_rt_ok)
    print("")
    return return_code


if __name__ == '__main__':
    main()
