
This tool will run a network test across multiple nodes and compare the results against IBM Spectrum Scale Key Performance Indicators (KPI).
This tool attempts to hide much of the complexity of running network measurement tools, and present the results in an easy to interpret way.

Note:  
**You need to first populate the hosts.json file with the IP addresses of the nodes to participate in the test.  Node names are not allowed.
Alternatively, you can pass the hosts as CSV string with a parameter**

This test can require a long time to execute, depending on the number of nodes. This tool will display an estimated  runtime at startup.

Remarks:
  - This tool runs on RedHat 7.5/7.6 on x86_64 and ppc64le architectures. At this point all nodes within a test must be of the same architecture.
  - Python 2.7.x is required, which is the default on Redhat 7.x systems.
  - Only Python standard libraries are used.
  - fping, gcc-c++ and psmisc must be installed on all nodes that participate in the test.  This tool will log an error if a required package is missing from any node.
  - SSH root passwordless access must be configured from the node that runs the tool to all the nodes that participate in the tests. This tool will log an error if any node does not meet this requirement.
  - The minimum FPING_COUNT value for a valid test must be 500, and a minimum of 10 (defaults to 500).
  - The minimum PERF_RUNTIME value for a valid test must be 1200, and a minimum of 30 (defaults to 1200).
  - The number of hosts must be between 4 and 32, inclusive.
  - This tool generates a log directory with all the raw data output for future comparisons
  - This tool returns 0 if all tests are passed in all nodes, and returns an integer > 0 if any errors are detected.
  - There is not RDMA support on throughput test at this time.
  - TCP port 6668 needs to be reachable and not in use in all nodes.
  - This tool needs to be run on a local filesystem.

KNOWN ISSUES:
  - There are no known issues at this time. If you encounter problems please contact IBM support or open an issue in our repository (https://github.ibm.com/SpectrumScaleTools/ECE_NETWORK_READINESS/issues)

TODO:
  - Add precompiled versions of throughput tool so no compiling is needed
  - Add RDMA support to throughput test
  - Add an option to load previous test results and compare

Usage statement:
```
# ./koet.py -h
usage: koet.py [-h] [-l KPI_LATENCY] [-c FPING_COUNT] [--hosts HOSTS_CSV]
               [-m KPI_THROUGHPUT] [-p PERF_RUNTIME] [-v]

optional arguments:
  -h, --help            show this help message and exit
  -l KPI_LATENCY, --latency KPI_LATENCY
                        The KPI latency value as float. The maximum required
                        value for certification is 1.0 msec
  -c FPING_COUNT, --fping_count FPING_COUNT
                        The number of fping counts to run per node and test.
                        The value has to be at least 2 seconds.The minimum
                        required value for certification is 500
  --hosts HOSTS_CSV     IP addreses of hosts on CSV format.Using this
                        overrides the hosts.json file.
  -m KPI_THROUGHPUT, --min_throughput KPI_THROUGHPUT
                        The minimum MB/sec required to pass the test. The
                        minimum required value for certification is 2000
  -p PERF_RUNTIME, --perf_runtime PERF_RUNTIME
                        The seconds of nsdperf runtime per test. The value has
                        to be at least 10 seconds.The minimum required value
                        for certification is 1200
  -v, --version         show program's version number and exit
```

An output example:
```
# ./koet.py

Welcome to KOET, version 1.1

JSON files versions:
	supported OS:		1.1
	packages: 		1.1

Please use https://github.com/IBM/SpectrumScale_NETWORK_READINESS to get latest versions and report issues about this tool.

The purpose of KOET is to obtain IPv4 network metrics for a number of nodes.

The latency KPI value of 1.0 msec is good to certify the environment

The fping count value of 500 ping per test and node is good to certify the environment

The throughput value of 600 MB/sec is good to certify the environment

The performance runtime value of 1200 second per test and node is good to certify the environment

It requires remote ssh passwordless between all nodes for user root already configured

This test run estimation is 850 minutes

This software comes with absolutely no warranty of any kind. Use it at your own risk

NOTE: The bandwidth numbers shown in this tool are for a very specific test. It is not a storage becnhmark.
They do not reflect that numbers you would see with  Spectrum Scale and your workload

Do you want to continue? (y/n):
```

At this point you can see the estimated runtime, consider using screen or alike. If you modify the number of fpings or the latency KPI you might see warning messages as below:
```
# ./koet.py -l 1.5 -c 100 -p 10 - m 100

Welcome to KOET, version 1.1

JSON files versions:
        supported OS:           1.1
        packages:               1.0

Please use https://github.com/IBM/SpectrumScaleTools  to get latest versions and report issues about KOET.

The purpose of KOET is to obtain IPv4 network metrics for a number of nodes.

WARNING: The latency KPI value of 1.5 msec is too high to certify the environment

WARNING: The fping count value of 100 pings per test and node is not enough to certify the environment

WARNING: The throughput value of 100 MB/sec is  not enough to certify the environment

WARNING: The performance runtime value of 10 second per test and node is not enough to certify the environment

It requires remote ssh passwordless between all nodes for user root already configured

This test run estimation is 50 minutes

This software comes with absolutely no warranty of any kind. Use it at your own risk

NOTE: The bandwidth numbers shown in this tool are for a very specific test. It is not a storage benchmark.
They do not necessarily reflect that numbers you would see with Spectrum Scale and your particular workload

Do you want to continue? (y/n): y
```

The following is the output of a successful run. Please notice that the output is colour coded.

```
OK: Red Hat Enterprise Linux Server 7.6 is a supported OS for this tool

OK: SSH with node 10.10.12.93 works
OK: SSH with node 10.10.12.92 works
OK: SSH with node 10.10.12.95 works
OK: SSH with node 10.10.12.94 works

Checking packages install status:

OK: on host 10.10.12.93 the psmisc installation status is as expected
OK: on host 10.10.12.93 the fping installation status is as expected
OK: on host 10.10.12.93 the gcc-c++ installation status is as expected
OK: on host 10.10.12.92 the psmisc installation status is as expected
OK: on host 10.10.12.92 the fping installation status is as expected
OK: on host 10.10.12.92 the gcc-c++ installation status is as expected
OK: on host 10.10.12.95 the psmisc installation status is as expected
OK: on host 10.10.12.95 the fping installation status is as expected
OK: on host 10.10.12.95 the gcc-c++ installation status is as expected
OK: on host 10.10.12.94 the psmisc installation status is as expected
OK: on host 10.10.12.94 the fping installation status is as expected
OK: on host 10.10.12.94 the gcc-c++ installation status is as expected
OK: on host 10.10.12.93 TCP port 6668 seems to be free
OK: on host 10.10.12.92 TCP port 6668 seems to be free
OK: on host 10.10.12.95 TCP port 6668 seems to be free
OK: on host 10.10.12.94 TCP port 6668 seems to be free

Starting ping run from 10.10.12.93 to all nodes
Ping run from 10.10.12.93 to all nodes completed

Starting ping run from 10.10.12.92 to all nodes
Ping run from 10.10.12.92 to all nodes completed

Starting ping run from 10.10.12.95 to all nodes
Ping run from 10.10.12.95 to all nodes completed

Starting ping run from 10.10.12.94 to all nodes
Ping run from 10.10.12.94 to all nodes completed

Starting throughput tests. Please be patient.

Starting throughput run from 10.10.12.93 to all nodes
Completed throughput run from 10.10.12.93 to all nodes

Starting throughput run from 10.10.12.92 to all nodes
Completed throughput run from 10.10.12.92 to all nodes

Starting throughput run from 10.10.12.95 to all nodes
Completed throughput run from 10.10.12.95 to all nodes

Starting throughput run from 10.10.12.94 to all nodes
Completed throughput run from 10.10.12.94 to all nodes

Starting many to many nodes throughput test
Completed Many to many nodes throughput test

Results for ICMP latency test 1:n
OK: on host 10.10.12.93 the 1:n average ICMP latency is 0.37 msec. Which is lower than the KPI of 1.0 msec
OK: on host 10.10.12.93 the 1:n maximum ICMP latency is 0.45 msec. Which is lower than the KPI of 2.0 msec
OK: on host 10.10.12.93 the 1:n minimum ICMP latency is 0.31 msec. Which is lower than the KPI of 1.0 msec
OK: on host 10.10.12.93 the 1:n standard deviation of ICMP latency is 0.02 msec. Which is lower than the KPI of 0.33 msec

OK: on host 10.10.12.92 the 1:n average ICMP latency is 0.27 msec. Which is lower than the KPI of 1.0 msec
OK: on host 10.10.12.92 the 1:n maximum ICMP latency is 0.44 msec. Which is lower than the KPI of 2.0 msec
OK: on host 10.10.12.92 the 1:n minimum ICMP latency is 0.17 msec. Which is lower than the KPI of 1.0 msec
OK: on host 10.10.12.92 the 1:n standard deviation of ICMP latency is 0.09 msec. Which is lower than the KPI of 0.33 msec

OK: on host 10.10.12.95 the 1:n average ICMP latency is 0.26 msec. Which is lower than the KPI of 1.0 msec
OK: on host 10.10.12.95 the 1:n maximum ICMP latency is 0.41 msec. Which is lower than the KPI of 2.0 msec
OK: on host 10.10.12.95 the 1:n minimum ICMP latency is 0.13 msec. Which is lower than the KPI of 1.0 msec
OK: on host 10.10.12.95 the 1:n standard deviation of ICMP latency is 0.08 msec. Which is lower than the KPI of 0.33 msec

OK: on host 10.10.12.94 the 1:n average ICMP latency is 0.26 msec. Which is lower than the KPI of 1.0 msec
OK: on host 10.10.12.94 the 1:n maximum ICMP latency is 0.44 msec. Which is lower than the KPI of 2.0 msec
OK: on host 10.10.12.94 the 1:n minimum ICMP latency is 0.17 msec. Which is lower than the KPI of 1.0 msec
OK: on host 10.10.12.94 the 1:n standard deviation of ICMP latency is 0.09 msec. Which is lower than the KPI of 0.33 msec

Results for throughput test
OK: on host 10.10.12.93 the throughput test result is 2354 MB/sec. Which is more than the KPI of 2000 MB/sec
OK: on host 10.10.12.92 the throughput test result is 2389 MB/sec. Which is more than the KPI of 2000 MB/sec
OK: on host 10.10.12.95 the throughput test result is 2312 MB/sec. Which is more than the KPI of 2000 MB/sec
OK: on host 10.10.12.94 the throughput test result is 2392 MB/sec. Which is more than the KPI of 2000 MB/sec
OK: the difference of bandwidth between nodes is 10.16% which is less than 20% defined on the KPI

The following metrics are not part of the KPI and are shown for informational purposes only
INFO: The maximum throughput value is 2466.0
INFO: The minimum throughput value is 2312.0
INFO: The mean throughput value is 2385.67
INFO: The standard deviation throughput value is 51.32
INFO: The average NSD latency for 10.10.12.93 is 117.172 msec
INFO: The average NSD latency for 10.10.12.92 is 19.0734 msec
INFO: The average NSD latency for all at the same time is 11.5054 msec
INFO: The average NSD latency for 10.10.12.95 is 16.941 msec
INFO: The average NSD latency for 10.10.12.94 is 16.8137 msec
INFO: The standard deviation of NSD latency for 10.10.12.93 is 5.46121 msec
INFO: The standard deviation of NSD latency for 10.10.12.92 is 18.9215 msec
INFO: The standard deviation of NSD latency for all at the same time is 20.145 msec
INFO: The standard deviation of NSD latency for 10.10.12.95 is 16.8196 msec
INFO: The standard deviation of NSD latency for 10.10.12.94 is 16.8328 msec
INFO: The packet Rx error count for throughput test on 10.10.12.93 is equal to 0 packet[s]
INFO: The packet Rx error count for throughput test on 10.10.12.92 is equal to 0 packet[s]
INFO: The packet Rx error count for throughput test on 10.10.12.95 is equal to 0 packet[s]
INFO: The packet Rx error count for throughput test on 10.10.12.94 is equal to 0 packet[s]
INFO: The packet Tx error count for throughput test on 10.10.12.93 is equal to 0 packet[s]
INFO: The packet Tx error count for throughput test on 10.10.12.92 is equal to 0 packet[s]
INFO: The packet Tx error count for throughput test on 10.10.12.95 is equal to 0 packet[s]
INFO: The packet Tx error count for throughput test on 10.10.12.94 is equal to 0 packet[s]
INFO: The packet retransmit count for throughput test on 10.10.12.93 is equal to 0 packet[s]
INFO: The packet retransmit count for throughput test on 10.10.12.92 is equal to 0 packet[s]
INFO: The packet retransmit count for throughput test on 10.10.12.95 is equal to 0 packet[s]
INFO: The packet retransmit count for throughput test on 10.10.12.94 is equal to 0 packet[s]
INFO: The packet Rx error count for throughput test on many to many is equal to 0 packet[s]
INFO: The packet Tx error count for throughput test on many to many is equal to 0 packet[s]
INFO: The packet retransmit count for throughput test many to many is equal to 0 packet[s]

The summary of this run:

        The 1:n fping average latency was successful in all
        The 1:n throughput test was successful in all nodes

OK: All tests had been passed. You can proceed with the next steps
```
