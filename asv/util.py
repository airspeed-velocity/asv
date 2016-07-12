# -*- coding: utf-8 -*-
# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""
Various low-level utilities.
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime
import json
import math
import os
import select
import signal
import subprocess
import struct
import sys
import time
import errno
import threading
import shutil
import stat

import six
from six.moves import xrange

from .console import log
from .extern import minify_json


WIN = (os.name == 'nt')

if not WIN:
    try:
        from select import PIPE_BUF
    except ImportError:
        # PIPE_BUF is not available on Python 2.6
        PIPE_BUF = os.pathconf('.', os.pathconf_names['PC_PIPE_BUF'])


TIMEOUT_RETCODE = -256


class UserError(Exception):
    pass


class ParallelFailure(Exception):
    """
    Custom exception to work around a multiprocessing bug
    https://bugs.python.org/issue9400
    """
    def __new__(cls, message, exc_cls, traceback_str):
        self = Exception.__new__(cls)
        self.message = message
        self.exc_cls = exc_cls
        self.traceback_str = traceback_str
        return self

    def __reduce__(self):
        return (ParallelFailure, (self.message, self.exc_cls, self.traceback_str))

    def __str__(self):
        return "{0}: {1}\n    {2}".format(self.exc_cls.__name__,
                                          self.message,
                                          self.traceback_str.replace("\n", "\n    "))

    def reraise(self):
        if self.exc_cls is UserError:
            raise UserError(self.message)
        else:
            raise self


def human_list(l):
    """
    Formats a list of strings in a human-friendly way.
    """
    l = ["'{0}'".format(x) for x in l]

    if len(l) == 0:
        return 'nothing'
    elif len(l) == 1:
        return l[0]
    elif len(l) == 2:
        return ' and '.join(l)
    else:
        return ', '.join(l[:-1]) + ' and ' + l[-1]


def human_file_size(size):
    """
    Returns a human-friendly string representing a file size
    that is 2-4 characters long.

    For example, depending on the number of bytes given, can be one
    of::

        256b
        64k
        1.1G

    Parameters
    ----------
    size : int
        The size of the file (in bytes)

    Returns
    -------
    size : str
        A human-friendly representation of the size of the file
    """
    size = float(size)

    suffixes = ' kMGTPEH'
    if size == 0:
        num_scale = 0
    else:
        num_scale = int(math.floor(math.log(size) / math.log(1000)))
    if num_scale > 7:
        suffix = '?'
    else:
        suffix = suffixes[num_scale]
    num_scale = int(math.pow(1000, num_scale))
    value = size / num_scale
    str_value = str(value)
    if str_value[2] == '.':
        str_value = str_value[:2]
    else:
        str_value = str_value[:3]
    return "{0:>3s}{1}".format(str_value, suffix)


def human_time(seconds):
    """
    Returns a human-friendly time string that is always exactly 6
    characters long.

    Depending on the number of seconds given, can be one of::

        1w 3d
        2d 4h
        1h 5m
        1m 4s
          15s

    Will be in color if console coloring is turned on.

    Parameters
    ----------
    seconds : int
        The number of seconds to represent

    Returns
    -------
    time : str
        A human-friendly representation of the given number of seconds
        that is always exactly 6 characters.
    """
    units = [
        ('ns', 0.000000001),
        ('μs', 0.000001),
        ('ms', 0.001),
        ('s', 1),
        ('m', 60),
        ('h', 60 * 60),
        ('d', 60 * 60 * 24),
        ('w', 60 * 60 * 24 * 7),
        ('y', 60 * 60 * 24 * 7 * 52),
        ('C', 60 * 60 * 24 * 7 * 52 * 100)
    ]

    seconds = float(seconds)

    for i in xrange(len(units) - 1):
        if seconds < units[i+1][1]:
            return "{0:.02f}{1}".format(seconds / units[i][1], units[i][0])
    return '~0'


def human_value(value, unit):
    """
    Formats a value in a given unit in a human friendly way.

    Parameters
    ----------
    value : anything
        The value to format

    unit : str
        The unit the value is in.  Currently understands `seconds` and `bytes`.
    """
    if isinstance(value, (int, float)):
        if value != value:
            # nan
            display = "n/a"
        elif unit == 'seconds':
            display = human_time(value)
        elif unit == 'bytes':
            display = human_file_size(value)
        else:
            display = json.dumps(value)
    elif value is None:
        display = "failed"
    else:
        display = json.dumps(value)

    return display


def which(filename):
    """
    Emulates the UNIX `which` command in Python.

    Raises an IOError if no result is found.
    """
    if WIN:
        if not filename.endswith('.exe'):
            filename = filename + '.exe'

    if os.path.sep in filename:
        locations = ['']
    else:
        locations = os.environ.get("PATH", "").split(os.pathsep)

        if WIN:
            # On windows, an entry in %PATH% may be quoted
            locations = [path[1:-1] if len(path) > 2 and path[0] == path[-1] == '"' else path
                         for path in locations]

    candidates = []
    for location in locations:
        candidate = os.path.join(location, filename)
        if os.path.isfile(candidate) or os.path.islink(candidate):
            candidates.append(candidate)
    if len(candidates) == 0:
        raise IOError("Could not find '{0}' in PATH".format(filename))
    return candidates[0]


def has_command(filename):
    """
    Returns `True` if the commandline utility exists.
    """
    try:
        which(filename)
    except IOError:
        return False
    else:
        return True


class ProcessError(subprocess.CalledProcessError):
    def __init__(self, args, retcode, stdout, stderr):
        self.args = args
        self.retcode = retcode
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        if self.retcode == TIMEOUT_RETCODE:
            return "Command '{0}' timed out".format(
                ' '.join(self.args))
        else:
            return "Command '{0}' returned non-zero exit status {1}".format(
                ' '.join(self.args), self.retcode)


def check_call(args, valid_return_codes=(0,), timeout=600, dots=True,
               display_error=True, shell=False, env=None, cwd=None):
    """
    Runs the given command in a subprocess, raising ProcessError if it
    fails.

    See `check_output` for parameters.
    """
    check_output(
        args, valid_return_codes=valid_return_codes, timeout=timeout,
        dots=dots, display_error=display_error, shell=shell, env=env,
        cwd=cwd)


def check_output(args, valid_return_codes=(0,), timeout=600, dots=True,
                 display_error=True, shell=False, return_stderr=False,
                 env=None, cwd=None):
    """
    Runs the given command in a subprocess, raising ProcessError if it
    fails.  Returns stdout as a string on success.

    Parameters
    ----------
    valid_return_codes : list, optional
        A list of return codes to ignore. Defaults to only ignoring zero.
        Setting to None ignores all return codes.

    timeout : number, optional
        Kill the process if it lasts longer than `timeout` seconds.

    dots : bool, optional
        If `True` (default) write a dot to the console to show
        progress as the subprocess outputs content.  May also be
        a callback function to call (with no arguments) to indicate
        progress.

    display_error : bool, optional
        If `True` (default) display the stdout and stderr of the
        subprocess when the subprocess returns an error code.

    shell : bool, optional
        If `True`, run the command through the shell.  Default is
        `False`.

    return_stderr : bool, optional
        If `True`, return both the (stdout, stderr, errcode) as a
        tuple.

    env : dict, optional
        Specify environment variables for the subprocess.

    cwd : str, optional
        Specify the current working directory to use when running the
        process.
    """
    def get_content(header=None):
        content = []
        if header is not None:
            content.append(header)
        content.extend([
            'STDOUT -------->',
            stdout[:-1],
            'STDERR -------->',
            stderr[:-1]
        ])

        return '\n'.join(content)

    if isinstance(args, six.string_types):
        args = [args]

    log.debug("Running '{0}'".format(' '.join(args)))

    posix = getattr(os, 'setpgid', None)
    if posix:
        # Run the subprocess in a separate process group, so that we
        # can kill it and all child processes it spawns e.g. on
        # timeouts. Note that subprocess.Popen will wait until exec()
        # before returning in parent process, so there is no race
        # condition in setting the process group vs. calls to os.killpg
        preexec_fn = lambda: os.setpgid(0, 0)
    else:
        preexec_fn = None

    proc = subprocess.Popen(
        args,
        close_fds=(not WIN),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=shell,
        preexec_fn=preexec_fn,
        cwd=cwd)

    last_dot_time = time.time()
    stdout_chunks = []
    stderr_chunks = []
    is_timeout = False

    if WIN:
        start_time = [time.time()]
        was_timeout = [False]

        def stdout_reader_run():
            while True:
                c = proc.stdout.read(1)
                if not c:
                    break
                start_time[0] = time.time()
                stdout_chunks.append(c)

        def stderr_reader_run():
            while True:
                c = proc.stderr.read(1)
                if not c:
                    break
                start_time[0] = time.time()
                stderr_chunks.append(c)

        def watcher_run():
            while proc.returncode is None:
                time.sleep(0.1)
                if time.time() - start_time[0] > timeout:
                    was_timeout[0] = True
                    proc.terminate()

        watcher = threading.Thread(target=watcher_run)
        watcher.start()

        stdout_reader = threading.Thread(target=stdout_reader_run)
        stdout_reader.start()

        stderr_reader = threading.Thread(target=stderr_reader_run)
        stderr_reader.start()

        try:
            proc.wait()
        finally:
            if proc.returncode is None:
                proc.terminate()
                proc.wait()
            watcher.join()
            stderr_reader.join()
            stdout_reader.join()

            proc.stdout.close()
            proc.stderr.close()

        is_timeout = was_timeout[0]
    else:
        try:
            if posix:
                # Forward signals related to Ctrl-Z handling; the child
                # process is in a separate process group so it won't receive
                # these automatically from the terminal
                def sig_forward(signum, frame):
                    _killpg_safe(proc.pid, signum)
                    if signum == signal.SIGTSTP:
                        os.kill(os.getpid(), signal.SIGSTOP)
                signal.signal(signal.SIGTSTP, sig_forward)
                signal.signal(signal.SIGCONT, sig_forward)

            fds = {
                proc.stdout.fileno(): stdout_chunks,
                proc.stderr.fileno(): stderr_chunks
                }

            while proc.poll() is None:
                try:
                    rlist, wlist, xlist = select.select(
                        list(fds.keys()), [], [], timeout)
                except select.error as err:
                    if err.args[0] == errno.EINTR:
                        # interrupted by signal handler; try again
                        continue
                    raise

                if len(rlist) == 0:
                    # We got a timeout
                    is_timeout = True
                    break
                for f in rlist:
                    output = os.read(f, PIPE_BUF)
                    fds[f].append(output)
                if dots and time.time() - last_dot_time > 0.5:
                    if dots is True:
                        log.dot()
                    elif dots:
                        dots()
                    last_dot_time = time.time()
        finally:
            if posix:
                # Restore signal handlers
                signal.signal(signal.SIGTSTP, signal.SIG_DFL)
                signal.signal(signal.SIGCONT, signal.SIG_DFL)

            if proc.returncode is None:
                # Timeout or another exceptional condition occurred, and
                # the program is still running.
                if posix:
                    # Terminate the whole process group
                    _killpg_safe(proc.pid, signal.SIGTERM)

                    for j in range(10):
                        time.sleep(0.1)
                        if proc.poll() is not None:
                            break
                    else:
                        # Didn't terminate within 1 sec, so kill it
                        _killpg_safe(proc.pid, signal.SIGKILL)
                else:
                    proc.terminate()
                proc.wait()

        proc.stdout.flush()
        proc.stderr.flush()

        stdout_chunks.append(proc.stdout.read())
        stderr_chunks.append(proc.stderr.read())

        proc.stdout.close()
        proc.stderr.close()

    stdout = b''.join(stdout_chunks)
    stderr = b''.join(stderr_chunks)

    stdout = stdout.decode('utf-8', 'replace')
    stderr = stderr.decode('utf-8', 'replace')

    if is_timeout:
        retcode = TIMEOUT_RETCODE
    else:
        retcode = proc.returncode

    if valid_return_codes is not None and retcode not in valid_return_codes:
        header = 'Error running {0}'.format(' '.join(args))
        if display_error:
            log.error(get_content(header))
        else:
            if log.is_debug_enabled():
                log.debug(get_content(header))
        raise ProcessError(args, retcode, stdout, stderr)
    elif log.is_debug_enabled():
        log.debug(get_content())

    if return_stderr:
        return (stdout, stderr, retcode)
    else:
        return stdout


def _killpg_safe(pgid, signo):
    """
    Same as os.killpg, but deal with OSX/BSD
    """
    try:
        os.killpg(pgid, signo)
    except OSError as exc:
        if exc.errno == errno.EPERM:
            # OSX/BSD may raise EPERM on killpg if the process group
            # already terminated
            pass
        else:
            raise


def write_json(path, data, api_version=None):
    """
    Writes JSON to the given path, including indentation and sorting.
    """
    path = os.path.abspath(path)

    dirname = long_path(os.path.dirname(path))
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    if api_version is not None:
        data = dict(data)
        data['version'] = api_version

    with long_path_open(path, 'w') as fd:
        json.dump(data, fd, indent=4, sort_keys=True)


def load_json(path, api_version=None, cleanup=True):
    """
    Loads JSON to the given path, ignoring any C-style comments.
    """
    path = os.path.abspath(path)

    with long_path_open(path, 'r') as fd:
        content = fd.read()

    if cleanup:
        content = minify_json.json_minify(content)
        content = content.replace(",]", "]")
        content = content.replace(",}", "}")

    try:
        d = json.loads(content)
    except ValueError as e:
        raise UserError(
            "Error parsing JSON in file '{0}': {1}".format(
                path, six.text_type(e)))

    if api_version is not None:
        if 'version' in d:
            if d['version'] < api_version:
                raise UserError(
                    "{0} is stored in an old file format.  Run "
                    "`asv update` to update it.".format(path))
            elif d['version'] > api_version:
                raise UserError(
                    "{0} is stored in a format that is newer than "
                    "what this version of asv understands.  Update "
                    "asv to use this file.".format(path))

            del d['version']
        else:
            raise UserError(
                "No version specified in {0}.".format(path))

    return d


def update_json(cls, path, api_version):
    """
    Perform JSON file format updates.

    Parameters
    ----------
    cls : object
        Object containing methods update_to_X which updates
        the given JSON tree from version X-1 to X.

    path : str
        Path to JSON file

    api_version : int
        The current API version
    """
    d = load_json(path)
    if 'version' not in d:
        raise UserError(
            "No version specified in {0}.".format(path))

    if d['version'] < api_version:
        for x in six.moves.xrange(d['version'] + 1, api_version):
            d = getattr(cls, 'update_to_{0}'.format(x), lambda x: x)(d)
        write_json(path, d, api_version)
    elif d['version'] > api_version:
        raise UserError(
            "version of {0} is newer than understood by this version of "
            "asv. Upgrade asv in order to use or add to these results.")


def iter_chunks(s, n):
    """
    Iterator that returns elements from s in chunks of size n.
    """
    chunk = []
    for x in s:
        chunk.append(x)
        if len(chunk) == n:
            yield chunk
            chunk = []
    if len(chunk):
        yield chunk


def pick_n(items, n):
    """Pick n items, attempting to get equal index spacing.
    """
    if not (n > 0):
        raise ValueError("Invalid number of items to pick")
    spacing = max(float(len(items)) / n, 1)
    spaced = []
    i = 0
    while int(i) < len(items) and len(spaced) < n:
        spaced.append(items[int(i)])
        i += spacing
    return spaced


def get_multiprocessing(parallel):
    """
    If parallel indicates that we want to do multiprocessing,
    imports the multiprocessing module and sets the parallel
    value accordingly.
    """
    if parallel != 1:
        import multiprocessing
        if parallel <= 0:
            parallel = multiprocessing.cpu_count()
        return parallel, multiprocessing
    return parallel, None


def iter_subclasses(cls):
    """
    Returns all subclasses of a class.
    """
    for x in cls.__subclasses__():
        yield x
        for y in iter_subclasses(x):
            yield y


def hash_equal(a, b):
    """
    Returns `True` if a and b represent the same commit hash.
    """
    min_len = min(len(a), len(b))
    return a.lower()[:min_len] == b.lower()[:min_len]


def get_cpu_info():
    """
    Gets a human-friendly description of this machine's CPU.

    Returns '' if it can't be obtained.
    """
    if sys.platform.startswith('linux'):
        with open("/proc/cpuinfo", "rb") as fd:
            lines = fd.readlines()
        for line in lines:
            if b':' in line:
                key, val = line.split(b':', 1)
                key = key.strip()
                val = val.strip()
                if key == b'model name':
                    return val.decode('ascii')
    elif sys.platform.startswith('darwin'):
        sysctl = which('sysctl')
        return check_output([sysctl, '-n', 'machdep.cpu.brand_string']).strip()
    return ''


def get_memsize():
    """
    Returns the amount of physical memory in this machine.

    Returns '' if it can't be obtained.
    """
    if sys.platform.startswith('linux'):
        with open("/proc/meminfo", "rb") as fd:
            lines = fd.readlines()
        for line in lines:
            if b':' in line:
                key, val = line.split(b':', 1)
                key = key.strip()
                val = val.strip()
                if key == b'MemTotal':
                    return int(val.split()[0])
    elif sys.platform.startswith('darwin'):
        sysctl = which('sysctl')
        return int(check_output([sysctl, '-n', 'hw.memsize']).strip())
    return ''


def _get_terminal_size_fallback():
    """
    Returns a tuple (height, width) containing the height and width of
    the terminal.  Fallback for when sys.get_terminal_size() doesn't
    exist or fails.
    """
    try:
        # Unix-specific code
        import fcntl
        import termios
        s = struct.pack(str("HHHH"), 0, 0, 0, 0)
        x = fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, s)
        (lines, width, xpixels, ypixels) = struct.unpack(str("HHHH"), x)
        if lines > 12:
            lines -= 6
        if width > 10:
            width -= 1
        return (lines, width)
    except:
        # Fall back on environment variables, or if not set, (25, 80)
        try:
            return (int(os.environ.get('LINES')),
                    int(os.environ.get('COLUMNS')))
        except TypeError:
            return 25, 80


def get_terminal_width():
    """
    Return the terminal width, or an estimate thereof.
    """
    try:
        # Python 3.3 and higher: this works under Windows and Unix
        return os.get_terminal_size().columns
    except (AttributeError, OSError):
        return _get_terminal_size_fallback()[1]


def format_text_table(rows, num_headers=0,
                      top_header_span_start=0,
                      top_header_text=None):
    """
    Format rows in as a reStructuredText table, in the vein of::

       ========== ========== ==========
       --         top header text, span start 1
       ---------- ---------------------
        row0col0     r0c1      r0c2
       ========== ========== ==========
        row1col0     r1c1      r1c2
        row2col0     r2c1      r2c2
       ========== ========== ==========

    """

    # Format content
    text_rows = [["{0}".format(item).replace("\n", " ") for item in row]
                 for row in rows]

    # Ensure same number of items on all rows
    num_items = max(len(row) for row in text_rows)
    for row in text_rows:
        row.extend(['']*(num_items - len(row)))

    # Determine widths
    col_widths = [max(len(row[j]) for row in text_rows) + 2
                  for j in range(num_items)]

    # Pad content
    text_rows = [[item.center(w) for w, item in zip(col_widths, row)]
                 for row in text_rows]

    # Generate result
    headers = [" ".join(row) for row in text_rows[:num_headers]]
    content = [" ".join(row) for row in text_rows[num_headers:]]
    separator = " ".join("-"*w for w in col_widths)

    result = []
    if top_header_text is not None:
        left_span = "-".join("-"*w for w in col_widths[:top_header_span_start])
        right_span = "-".join("-"*w for w in col_widths[top_header_span_start:])
        if left_span and right_span:
            result += ["--" + " " * (len(left_span)-1) + top_header_text.center(len(right_span))]
            result += [" ".join([left_span, right_span])]
        else:
            result += [top_header_text.center(len(separator))]
            result += ["-".join([left_span, right_span])]
        result += headers
        result += [separator.replace("-", "=")]
    elif headers:
        result += headers
        result += [separator]
    result += content
    result = [separator.replace("-", "=")] + result
    result += [separator.replace("-", "=")]
    return "\n".join(result)


def datetime_to_timestamp(dt):
    """
    Convert a Python datetime object to a UNIX timestamp.
    """
    if sys.version_info[:2] < (2, 7):
        def total_seconds(td):
            return (td.microseconds +
                    (td.seconds + td.days * 24 * 3600) * 1e6) / 1e6
    else:
        def total_seconds(td):
            return td.total_seconds()

    return int(total_seconds(dt - datetime.datetime(1970, 1, 1)))


def datetime_to_js_timestamp(dt):
    """
    Convert a Python datetime object to a Javascript timestamp.
    """
    return 1000 * datetime_to_timestamp(dt)


def is_nan(x):
    """
    Returns `True` if x is a NaN value.
    """
    if isinstance(x, float):
        return x != x
    return False


if not WIN:
    long_path_open = open
    long_path_rmtree = shutil.rmtree
    def long_path(path):
        return path
else:
    def long_path(path):
        if path.startswith("\\\\"):
            return path
        return "\\\\?\\" + os.path.abspath(path)

    def _remove_readonly(func, path, exc_info):
        """Clear the readonly bit and reattempt the removal;
        Windows rmtree doesn't do this by default"""
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def long_path_open(filename, *a, **kw):
        return open(long_path(filename), *a, **kw)

    def long_path_rmtree(path, ignore_errors=False):
        if ignore_errors:
            onerror = None
        else:
            onerror = _remove_readonly
        shutil.rmtree(long_path(path),
                      ignore_errors=ignore_errors,
                      onerror=onerror)
