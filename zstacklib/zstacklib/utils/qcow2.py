import log
import os
import plugin
import traceable_shell
import report
import linux
import tempfile

logger = log.get_logger(__name__)


def already_template_of(src, dst):
    """Return True iff `dst` already exists as a self-contained qcow2 file
    (no backing) whose virtual size matches `src` -- i.e. an earlier
    create_template(src, dst) call already finished. Used as an idempotency
    guard for retried merge_snapshot HTTP requests.

    Conservative: any error in inspection -> False (re-do the work).
    """
    try:
        if not os.path.exists(dst):
            return False
        if linux.qcow2_get_backing_file(dst):
            return False
        if int(linux.qcow2_virtualsize(dst)) != int(linux.qcow2_virtualsize(src)):
            return False
        return True
    except Exception as e:
        logger.debug('already_template_of(%s,%s) check failed: %s' % (src, dst, e))
        return False


def backing_chain_already_collapsed(snapshots):
    """For a list of snapshot file paths [s0, s1, s2, ...] where the caller
    intends to rebase s_i to point at s_{i+1}, return True if every adjacent
    pair already has the expected backing relationship.

    Used by merge_and_rebase_snapshot to skip rebases that have all already
    happened in a previous (interrupted) call.
    """
    try:
        for i in range(len(snapshots) - 1):
            target = snapshots[i]
            expected_backing = snapshots[i + 1]
            if linux.qcow2_get_backing_file(target) != expected_backing:
                return False
        return True
    except Exception as e:
        logger.debug('backing_chain check failed: %s' % e)
        return False


def create_template_with_task_daemon(src, dst, task_spec, dst_format='qcow2', opts=None, **daemonargs):
    t_shell = traceable_shell.get_shell(task_spec)
    p_file = tempfile.mktemp()

    class ConvertTaskDaemon(plugin.TaskDaemon):

        def __init__(self, dst_path, task_spec):
            super(ConvertTaskDaemon, self).__init__(task_spec, 'ConvertImage')
            self.task_spec = task_spec
            self.dst_path = dst_path
            self.__dict__.update(daemonargs)

        def _exit(self, exc_type, exc_val, exc_tb):
            linux.rm_file_force(p_file)

        def _cancel(self):
            traceable_shell.cancel_job_by_api(self.api_id)
            linux.rm_file_force(self.dst_path)

        # get percent from (75.65/100%)
        def _get_percent(self):
            p = linux.tail_1(p_file, split=b"\r")
            if not p or "%" not in p:
                return None

            percent = p.strip().lstrip("(").split("/")[0]
            return report.get_exact_percent(percent, self.stage)

    with ConvertTaskDaemon(dst, task_spec):
        linux.create_template(src, dst, dst_format=dst_format, shell=t_shell, progress_output=p_file, opts=opts)
