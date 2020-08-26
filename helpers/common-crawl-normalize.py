#!/usr/bin/python3
# -*- coding: utf-8 -*-

### Code made available on https://github.com/adbar/url-tools under GPL license.
### Adrien Barbaresi, 2015.

# Purpose: Revert URLs to their usual form


from __future__ import print_function

import argparse
import re
import time


parser = argparse.ArgumentParser()
parser.add_argument('-i', '--inputfile', dest='inputfile', help='name of the input file', required=True)
parser.add_argument('-o', '--outputfile', dest='outputfile', help='name of the output file', required=True)
args = parser.parse_args()

start_time = time.time()
lastseen = ''


with open(args.outputfile, 'w') as outputfh:
    with open(args.inputfile, 'r') as inputfh:
        for line in inputfh:
            # strip
            line = line.rstrip()
            # deduplicate
            if line is not lastseen:
                lastseen = line
                # reorder
                if re.search(r':http$', line):
                    line = re.sub(r':http$', '', line)

                    # normalize URL problem
                    line = re.sub(r'\./', '/', line, 1)

                    # not elegant, but will do the trick
                    match = re.match(r'(.+?)/', line)
                    if match:
                        core = match.group(1)
                    else:
                        print ('ERROR: Curious one (1):', lastseen)
                        continue
                    if not re.search(r'\.', core):
                        print ('ERROR: Curious one (2):', lastseen)
                        continue
                    elements = re.findall(r'.+?\.', core)
                    match = re.search(r'\.([^\.]+)$', core)
                    if match:
                        lastone = match.group(1)
                    else:
                        print ('ERROR: Curious one (3):', lastseen)
                        continue

                    # print the result of the substitution
                    core = ''
                    for item in reversed(elements):
                        core += item
                    core = re.sub(r'\.$', '', core)
                    line = re.sub(r'^.+?/', '/', line)
                    line = 'http://' + lastone + '.' + core + line
                    outputfh.write(line + '\n')


exec_time = time.time() - start_time
print ('# exec time:\t\t{0:.2f}' . format(exec_time))
