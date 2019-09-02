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
    - Added check for rare (not manage to reproduce in lab) case whre nsdperf fails to generate JSON
