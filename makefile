# Makefile for net programs
CXX = g++
LIBS = -lpthread -lrt
CFLAGS = -O2

PROGS = nsdperf

all: $(PROGS)

clean:
	rm -f $(PROGS)

$(PROGS): nsdperf.C
	$(CXX) $(CFLAGS) -o $@ nsdperf.C $(LIBS)
