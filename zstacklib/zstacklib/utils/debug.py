__author__ = 'frank'

import time

import linux
import traceback
import signal
import sys
import threading
import operator
import gc
import objgraph
import lock
import inspect
import datetime
import os
from types import *
try:
    from types import InstanceType
except ImportError:
    # Python 3.x compatibility
    InstanceType = None

try:
    iteritems = dict.iteritems
except AttributeError:
    # Python 3.x compatibility
    iteritems = dict.items

from zstacklib.utils import log
from zstacklib.utils import thread

logger = log.get_logger(__name__)


def dump(sig, frame):
    message = "Signal received : dump Traceback:\n"
    message += ''.join(traceback.format_stack(frame))
    print message


def install_runtime_tracedumper():
    signal.signal(signal.SIGUSR2, dump_debug_info)


def dump_stack():
    message = "Stack Traceback:\n"
    message += ''.join(traceback.format_stack())
    return message


def dump_debug_info(signum, fram, *argv):
    try:
        thread.ThreadFacade.run_in_thread(dump_threads)
        thread.ThreadFacade.run_in_thread(dump_objects)
        thread.ThreadFacade.run_in_thread(track_objects)
    except Exception as e:
        logger.warn("get error when dump debug info %s" % e.message)



def dump_threads():
    logger.debug('dumping threads')
    output = []
    threads = 0
    current_frames = sys._current_frames()

    for th in threading.enumerate():
        threads += 1
        thread_info = []
        thread_info.append("Thread: {}, ID: {}".format(th.name, th.ident))

        if th.ident in current_frames:
            try:
                stack = traceback.format_stack(current_frames[th.ident])
                thread_info.append("".join(stack))

                thread_locals = current_frames[th.ident].f_locals
                simplified_locals = {k: repr(v)[:100] for k, v in thread_locals.items()}
                thread_info.append("Locals: {}".format(simplified_locals))
            except Exception as e:
                logger.debug("Error dumping thread {}: {}".format(th.name, str(e)))

        output.append("\n".join(thread_info))

    full_output = "There are {} threads:\n{}".format(threads, "\n\n".join(output))
    logger.debug(full_output)
    return


def objects_filter(target):
    # remove undesired objects from the graph
    # if inspect.isframe(target) and target.f_code and "objgraph.py" in target.f_code.co_filename:
    #     return False
    # elif isinstance(target, tuple) and len(target) > 0 and target[0] == "tuple id":
    #     return False
    if inspect.isfunction(target):
        return False
    return True

def show_backrefs_for_new_objects(new_objects, output=None):
    class Writer:
        def __init__(self, fd):
            self.fd = fd
            self.buffer = bytearray()
        def write(self, context):
            self.buffer.extend(context)
            if len(self.buffer) >= 1048576:
                self.fd.write(self.buffer)
                self.fd.flush()
                self.buffer = bytearray()

        def close(self):
            if len(self.buffer) > 0:
                self.fd.write(self.buffer)
                self.fd.flush()
            self.fd.close()


    try:
        with open(output, 'w') as fd:
            # output = Writer(fd)
            objgraph.show_backrefs(new_objects, max_depth=10, filter=objects_filter, output=fd)
    except Exception as e:
        print ("get an error on parsing objects back references: %s" % str(e))

def show_backref(obj_types):
    # find back ref
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S').replace(" ", "-")
    for obj_type in obj_types:
        objs = objgraph.by_type(obj_type)
        if not objs:
            continue
        objs = objs[:3]
        # backref_chain = objgraph.find_backref_chain(new_objs[0], lambda z: type(z) == FrameType)
        # if len(backref_chain) >= 2 and type(backref_chain[0]) == FrameType:
        #     # found ref by stack frame directly
        #     res.append("object %s ref by stack: %s" % ())
        #     pass
        show_backrefs_for_new_objects(objs, output=os.path.join('./', "%s-%s.dot" % (now, obj_type)))

        del objs
        # show_refs_for_new_objects(new_objs, output=os.path.join(dot_dir, "%s-%d-%s-ref.dot" % (now, idx, name)))



def log_objs_statistics(total_num_stats, total_size_stats, num_deltas, size_deltas, all_total_size, all_total_num):
    res = []
    total_size_list = sorted(total_size_stats.items(), key=operator.itemgetter(1), reverse=True)
    width = max(len(name) for name, size in total_size_list)
    res.append("Total size = %s bytes. Total objects num = %s." % (all_total_size, all_total_num))
    res.append('%5s %-*s %12s %5s %12s %5s %12s %5s %12s %5s' % ("Index", width, "Kind", "Size", "%", "Growth", "%", "Count", "%", "Growth", "%"))
    idx = 0
    for name, total_size in total_size_list:
        total_num = total_num_stats.get(name, 0)
        size_delta = size_deltas.get(name, 0)
        num_delta = num_deltas.get(name, 0)
        res.append('%5d %-*s %12d %5d %+12d %+5d %12d %5d %+12d %+5d' % (idx, width, name, total_size, float(total_size)*100/all_total_size,
                                                                         size_delta, float(size_delta)*100/all_total_size, total_num, float(total_num)*100/all_total_num,
                                                                         num_delta, float(num_delta)*100/all_total_num))
        idx += 1

    print ('\n'.join(res))

def num_and_size_stats(objects=None, shortname=False):
    if objects is None:
        objects = gc.get_objects()
    try:
        if shortname:
            typename = _short_typename
        else:
            typename = _long_typename
        num_stats = {}
        # type_id_dict = {}
        size_stats = {}
        total_num = len(objects)
        total_size = 0
        for o in objects:
            n = typename(o)
            if "__builtin__" in n:
                continue
            num_stats[n] = num_stats.get(n, 0) + 1
            obj_size = sys.getsizeof(o)
            size_stats[n] = size_stats.get(n, 0) + obj_size
            total_size += obj_size
            # ids = type_id_dict.get(n, set())
            # ids.add(id(o))
            # type_id_dict[n] = ids

        return num_stats, size_stats, total_num, total_size
    finally:
        del objects  # clear cyclic references to frame


def track_objects(times=3, interval=3):
    gc.collect()

    old_num_stats, old_size_stats, total_num, total_size = num_and_size_stats()
    log_objs_statistics(old_num_stats, old_size_stats, {}, {}, total_num, total_size)
    always_exists_obj_type = set(old_size_stats.keys())

    cnt = 1
    while cnt <= times:
        print("tracking the growth of objects:(%d/%d)" % (cnt, times))
        cnt += 1
        time.sleep(interval)

        cur_num_stats, cur_size_stats, total_num, total_size = num_and_size_stats()
        always_exists_obj_type = always_exists_obj_type & set(cur_size_stats.keys())

        # Calculate the memory increment of objects
        num_deltas = {}
        size_deltas = {}
        # obj_ids_deltas = {}
        for name, size in iteritems(cur_size_stats):
            old_size = old_size_stats.get(name, 0)
            if size > old_size:
                size_deltas[name] = size - old_size
                num_deltas[name] = cur_num_stats[name] - old_num_stats.get(name, 0)
                # obj_ids_deltas[name] = cur_type_id_dict[name] - old_type_id_dict.get(name, set())

            old_num_stats[name] = cur_num_stats[name]
            old_size_stats[name] = cur_size_stats[name]
            # old_type_id_dict[name] = cur_type_id_dict[name]

        log_objs_statistics(cur_num_stats, cur_size_stats, num_deltas, size_deltas, total_size, total_num)

    print always_exists_obj_type
    show_backref(always_exists_obj_type)
    return


def dump_objects():
    logger.debug('dumping objects')
    stats = sorted(
        typestats().items(), key=operator.itemgetter(1), reverse=True)
    logger.debug(stats)
    return


def typestats(objects=None, shortnames=False, filter=None):
    if objects is None:
        objects = gc.get_objects()
    try:
        if shortnames:
            typename = _short_typename
        else:
            typename = _long_typename
        stats = {}
        for o in objects:
            if filter and not filter(o):
                continue
            n = typename(o)
            stats[n] = stats.get(n, 0) + 1
        return stats
    finally:
        del objects  # clear cyclic references to frame


def _short_typename(obj):
    return _get_obj_type(obj).__name__


def _long_typename(obj):
    objtype = _get_obj_type(obj)
    name = objtype.__name__
    module = getattr(objtype, '__module__', None)
    if module:
        return '%s.%s' % (module, name)
    else:
        return name


def _get_obj_type(obj):
    objtype = type(obj)
    if type(obj) == InstanceType:
        objtype = obj.__class__
    return objtype
