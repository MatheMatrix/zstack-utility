#!/usr/bin/env python

"""
Given an API or task UUID, dump its execution timeline.  For example,
with API UUID "8a5b9ff4a7294446a5a765c8dc793912":

$ cat mn.log | zstack-ctl timeline -k 8a5b9ff4a7294446a5a765c8dc793912
$ zcat mn-{1,2}.log.gz | zstack-ctl timeline -k 8a5b9ff4a7294446a5a765c8dc793912

This program can optionally (with '-p') generate a Gnuplot script
{uuid}.plt to visualize the time consumption with a Gantt Chart.

$ gnuplot 8a5b9ff4a7294446a5a765c8dc793912.plt

"""

from argparse import ArgumentParser, RawTextHelpFormatter
from datetime import datetime

import json, re, sys

class TaskLet(object):
    def __init__(self):
        self.begin_time = None
        self.end_time = None
        self.task_type = None
        self.task_id = None
        self.__duration = None

    # should be overridden for meaningful description
    def get_task_name(self):
        return self.task_id

    def get_duration(self):
        if self.__duration is not None:
            return self.__duration

        if self.begin_time and self.end_time:
            d1 = parse_timestamp(self.begin_time)
            d2 = parse_timestamp(self.end_time)
            self.__duration = (d2 - d1).total_seconds()
        else:
            self.__duration = -1

        return self.__duration

    def __lt__(self, other):
        return self.get_duration() < other.get_duration()

    def __str__(self):
        return "{} {}: {} {}".format(self.task_type, self.task_id, self.begin_time, self.end_time)

def parse_timestamp(timestamp):
    return datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f')


def compact_line(line, length):
    return line if len(line) <= length else line[:(length-3)]+"..."


class CloudBusTask(TaskLet):
    def __init__(self, msgid):
        super(CloudBusTask, self).__init__()
        self.task_type = "MESG"
        self.msg_name = None
        self.reply_name = None
        self.task_id = msgid

    def get_task_name(self):
        return self.msg_name.split(".")[-1]

    def __str__(self):
        return "{} -> {} {}: {}".format(self.begin_time, self.end_time, self.task_type, self.msg_name.split(".")[-1])

class DispatchQueueTask(TaskLet):
    def __init__(self, taskname):
        super(DispatchQueueTask, self).__init__()
        self.task_type = "DSPQ"
        self.task_id = taskname

    def __str__(self):
        return "{} -> {} {}: {}".format(self.begin_time, self.end_time, self.task_type, self.task_id)

class RESTRequestTask(TaskLet):
    def __init__(self, url, taskuuid):
        super(RESTRequestTask, self).__init__()
        self.task_type = "POST"
        self.task_id = taskuuid
        self.req_url = url

    def get_task_name(self):
        return self.req_url

    def __str__(self):
        return "{} -> {} {}: {}".format(self.begin_time, self.end_time, self.task_type, self.req_url)

class FlowChainTask(TaskLet):
    def __init__(self, fcid, name):
        super(FlowChainTask, self).__init__()
        self.task_type = "FLOW"
        self.task_id = fcid
        self.flow_name = name

    def get_task_name(self):
        return self.flow_name

    def __str__(self):
        return "{} -> {} {}: {}".format(self.begin_time, self.end_time, self.task_type, self.flow_name)

def parse_message(name, jsonstr):
    msgobj = json.loads(jsonstr).get(name)
    if name.endswith("Msg") or name.endswith("CanonicalEvent"):
        return msgobj.get("id"), False
    if name.endswith("Event"):
        return msgobj.get("apiId"), True
    return msgobj.get("headers").get("correlationId"), True


# The format of log record:
# date       time     log-level  component  api/task-id  leftover
# 2021-03-31 18:58:30,008 DEBUG [CloudBusImpl3] {} (main) registered service
#                                                  ^
#                                                  `---- leftover starts here
def get_cloudbus_task(timestamp, leftover):
    xs = leftover.split(" ", 4)
    if len(xs) != 5 or "received" not in xs[2]:
        return None

    msgname = xs[3]
    #if msgname.endswith("CanonicalEvent"):
    #    return None

    msgid, isreply = parse_message(msgname, xs[4])
    task = CloudBusTask(msgid)
    if isreply:
        task.end_time = timestamp
        task.reply_name = msgname
    else:
        task.begin_time = timestamp
        task.msg_name = msgname

    return task

def get_dispatch_queue_task(timestamp, leftover):
    matched = re.search(r'\([\d\w-]+\) (\w+) executing runningQueue:(.*), task name: (.*)$', leftover)
    if not matched:
        return None

    # group(0) - the whole matched string
    # group(2) - the queue name
    act, taskname = matched.group(1), matched.group(3)
    task = DispatchQueueTask(taskname)
    if act == "Start":
        task.begin_time = timestamp
    elif act == "Finish":
        task.end_time = timestamp
    else:
        return None

    return task


def get_restreq_task(timestamp, leftover):
    begin, matched = True, None
    if ") json POST [" in leftover:
        matched = re.search(r'json\s\w+\s\[(http:.*?)\].*taskuuid=\[([\d\w]{32})', leftover)
    elif "[http response(" in leftover:
        matched = re.search(r'url:\s(http:.*?),\staskUuid:\s([\d\w]{32})', leftover)
        begin = False

    if not matched:
        return None

    url, taskuuid = matched.group(1), matched.group(2)
    task = RESTRequestTask(url, taskuuid)
    if begin:
        task.begin_time = timestamp
    else:
        task.end_time = timestamp

    return task

def get_flowchain_task(timestamp, leftover):
    matched = re.search(r'.*FlowChain\(FCID_([\d\w]+)\): (.*)] (.*)$', leftover)
    if not matched:
        return None

    fcid, name, act = matched.group(1), matched.group(2), matched.group(3)
    task = FlowChainTask(fcid, name)
    if act == "starts":
        task.begin_time = timestamp
    elif act.startswith("successfully completed") or act.startswith("rolled back all"):
        task.end_time = timestamp
    else:
        return None

    return task


parserTable = {
    "CloudBusImpl3":     get_cloudbus_task,
    "DispatchQueueImpl": get_dispatch_queue_task,
    "RESTFacadeImpl":    get_restreq_task,
    "SimpleFlowChain":   get_flowchain_task,
}

def readlines(reader):
    while True:
        line = reader.readline()
        if not line:
            break
        yield line


def get_task(line, uuid):
    xs = line.split(" ", 5)
    if len(xs) < 5:
        return None

    date, time, component, apiid = xs[0], xs[1], xs[3], xs[4]
    if uuid not in apiid:
        return None

    try:
        timestamp = (date + " " + time).replace(",", ".")
        return parserTable[component.strip("[]")](timestamp, xs[5])
    except KeyError:
        return None


class TaskTimeline(object):
    def __init__(self):
        self.tasks = []         # For simplicity, one list for all tasks.
        self.pending = 0        # Number of pending tasks.
        self.logs = []

    def _complete_task(self, task):
        for t in self.tasks:
            if t.end_time: continue
            if t.task_type == task.task_type and t.task_id == task.task_id:
                t.end_time = task.end_time
                self.pending -= 1


    def _add_new_task(self, task):
        self.tasks.append(task)
        self.pending += 1

    def add_task(self, task):
        if task.begin_time or not self.tasks:
            self._add_new_task(task)
        else:
            self._complete_task(task)

    # def build(self, reader, uuid):
    #     for line in readlines(reader):
    #         task = get_task(line, uuid)
    #         if not task:
    #             continue

    #         self.add_task(task)
    #         if self.pending == 0:
    #             break

    def _build(self, uuid, line):
        task = get_task(line, uuid)
        if not task:
            return

        self.add_task(task)
        if self.pending == 0:
            return

    def build(self, reader, uuid, collect_log=False):
        for line in readlines(reader):
            if collect_log and uuid in line:
                self.logs.append(line)

            self._build(uuid, line)

    def _dumptask(self, writer, t):
        s = "{:>10} {}".format(t.get_duration(), t)
        writer.write(compact_line(s, 140))
        writer.write("\n")

    def dumpflow(self, writer, top):
        writer.write("# total {}, order by start time:\n".format(len(self.tasks)))
        for t in self.tasks:
            self._dumptask(writer, t)

        ncomp = [ t for t in self.tasks if t.end_time is None ]
        if len(ncomp) > 0:
            writer.write("\n\n# log incomplete, end time not found for the following:\n")
            for t in ncomp:
                writer.write("  {} {}: {}\n".format(t.begin_time, t.task_type, t.get_task_name()))

        if top < 1:
            return

        writer.write("\n\n# top {}:\n".format(top))
        self.tasks.sort(reverse=True)
        for t in self.tasks[:top]:
            self._dumptask(writer, t)

    def generate_gantt(self, fname):
        if not self.tasks:
            return

        with open(fname+".plt", 'w') as out:
            out.write("# Simple Gantt chart with Gnuplot\n")
            out.write("# Generated with <3 by qun.li@zstack.io\n")
            out.write("$DATA << EOD\n")
            out.write("# Task      start          end\n")

            for t in self.tasks:
                if not t.end_time: continue
                out.write("{},{},{}\n".format(compact_line(t.get_task_name(), 32), t.begin_time, t.end_time))

            out.write("EOD\n\n")
            out.write('set output "{}"\n'.format(fname+".png"))
            out.write('set title "{/=12 Timeline Gantt Chart}\\n\\n{/:Bold key: %s}"\n' % fname)

            out.write("""set term pngcairo size 1280,800
set datafile separator ","
set xdata time
set timefmt "%Y-%m-%d %H:%M:%S"
set format x "%M:%S"

set autoscale x
set grid x y
unset key

set border 3

# define arrow style 1
set style arrow 1 filled size screen 0.01,15,45 fixed lt 3 lw 2

timeformat = "%Y-%m-%d %H:%M:%S"
T(N) = timecolumn(N,timeformat)

# 2D vectors:
#  (x,y) to (x+xdelta, y+ydelta)
#
# 4 columns:
#  x    y    xdelta    ydelta
plot $DATA using (timecolumn(2)) : ($0) : (T(3)-T(2)) : (0.0) : yticlabel(1) with vector as 1
""")

if __name__ == '__main__':
    parser = ArgumentParser("timeline", description=__doc__, formatter_class=RawTextHelpFormatter)
    parser.add_argument('-k', '--key', required=True, default="", help='the API or task UUID for search')
    parser.add_argument('-t', '--top', type=int, default=0, help='show top N time consumers')
    parser.add_argument('-p', '--plot', action='store_true', help='generate a Gnuplot script')
    args = parser.parse_args()

    timeline = TaskTimeline()
    timeline.build(sys.stdin, args.key)
    timeline.dumpflow(sys.stdout, args.top)

    if args.plot: timeline.generate_gantt(args.key)

# vim: set et ts=4 sw=4 ai:
