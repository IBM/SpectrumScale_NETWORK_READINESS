Changelog:


- 1.0:
    - Initial release.

- 1.1:
    - Added NSD latency
    - Rx, Tx and retransmit stats
    - Added hosts as parameter
    - PEP8 compliant
    - Minor cosmetic fixes

- 1.2:
    - hosts.json can now we generated from cli input
    - moved from net-tools to iproute and added check for it

- 1.3
    - Initial implementation to run on both python3 and python2

- 1.4
    - Added check for rare (not manage to reproduce in lab) case where nsdperf fails to generate JSON

- 1.5
    - Initial implementation of RDMA throughput tests with nsdperf backend
    - Changed minimum number of hosts from 4 to 2
    - Changed maximum number of nodes from 32 to 64
    - Added option to bypass RPM SW checks
    - Minor cosmetic changes

- 1.6
    - Added support for RHEL 8.0 and RHEL 7.7
    - Minor cosmetic changes

- 1.7
    - More accurate RDMA NSD latency calculation
    - Added check for POSIX ACL of needed files
    - Add warning about RDMA ports UP state as reported by ibdev2netdev
    - Minor cosmetic changes

- 1.8
    - Lower severity of ICMP latency results when using RDMA
    - Added check for firewalld
    - Added LogLevel=error for ssh connections to ignore banners
    - Minor cosmetic changes

- 1.9
    - Fixed issue of nsdperf that made NSD latencies show much bigger than real on x86_64 systems

- 1.10
    - Fixed issue with two nodes test on python3. New min number of nodes is 3 (STG Defect 241194)
    - Mitigated issue of extra SSH lines that messed up the nsdperf wrapper on a corner case of ssh host keys (STG Defect 241193)
