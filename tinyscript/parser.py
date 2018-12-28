#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""Module for defining argument parser-related functions and objects.

"""
import argparse
import atexit
import os
import re
import sys
from inspect import getmembers, isfunction, ismethod
from os.path import basename, splitext

from .__info__ import __author__, __copyright__, __version__
from .argreparse import *
from .handlers import *
from .loglib import *
from .report import Report
from .step import set_step_items


__all__ = __features__ = ["parser", "initialize", "validate"]


def __get_calls_from_parser(proxy_parser, real_parser):
    """
    This actually executes the calls registered in the ProxyArgumentParser.

    :param proxy_parser: ProxyArgumentParser instance
    :param real_parser:  ArgumentParser instance
    """
    __parsers[proxy_parser] = real_parser
    for method, safe, args, kwargs, proxy_subparser in proxy_parser.calls:
        args = (__proxy_to_real_parser(v) for v in args)
        kwargs = {k: __proxy_to_real_parser(v) for k, v in kwargs.items()}
        real_subparser = getattr(real_parser, method)(*args, **kwargs)
        if real_subparser is not None:
            __get_calls_from_parser(proxy_subparser, real_subparser)


def __proxy_to_real_parser(value):
    """
    This recursively converts ProxyArgumentParser instances to actual parsers.

    Use case: defining subparsers with a parent
      >>> [...]
      >>> parser.add_argument(...)  # argument common to all subparsers
      >>> subparsers = parser.add_subparsers()
      >>> subparsers.add_parser(..., parents=[parent])
                                                ^
                              this is an instance of ProxyArgumentParser
                              and must be converted to an actual parser instance

    :param value: a value coming from args or kwargs aimed to an actual parser
    """
    if isinstance(value, ProxyArgumentParser):
        return __parsers[value]
    elif any(isinstance(value, t) for t in [list, tuple]):
        new_value = []
        for subvalue in iter(value):
            new_value.append(__proxy_to_real_parser(subvalue))
        return new_value
    return value


def initialize(glob, sudo=False, multi_debug_level=False, add_config=False,
               add_demo=False, add_step=False, add_version=False,
               add_wizard=False, noargs_action=None, report_func=None):
    """
    Initialization function ; sets up the arguments for the parser and creates a
     logger to be inserted in the input dictionary of global variables from the
     calling script.

    :param glob:              globals() instance from the calling script
    :param sudo:              if True, require sudo credentials and re-run
                               script with sudo
    :param multi_debug_level: allow to use -v, -vv, -vvv (adjust logging level)
                               instead of just -v (only debug on/off)
    :param add_config:        add an option to input an INI configuration file
    :param add_demo:          add an option to re-run the process using a random
                               entry from the __examples__ (only works if this
                               variable is populated)
    :param add_step:          add an execution stepping option
    :param add_version:       add a version option
    :param add_wizard:        add an option to run a wizard, asking for each
                               input argument
    :param noargs_action:     action to be performed when no argument is input
    :param report_func:       report generation function
    """
    global parser, __parsers
    
    add = {'config': add_config, 'demo': add_demo, 'help': True,
           'step': add_step, 'version': add_version, 'wizard': add_wizard}
    glob['parser'] = p = ArgumentParser(glob)
    # 1) handle action when no input argument is given
    add['demo'] = add['demo'] and glob['parser'].examples
    noarg = len(sys.argv) == 1
    if noarg and noargs_action:
        assert noargs_action in add.keys(), \
               "Bad action when no args (should be one of: {})" \
               .format('|'.join(add.keys()))
        add[noargs_action] = True  # ensure this action is enabled, even if it
                                   #  is not given the passed arguments
    # 2) if sudo required, restart the script
    if sudo:
        # if not root, restart the script in another process and jump to this
        if os.geteuid() != 0:
            python = [] if glob['__file__'].startswith("./") else ["python"]
            os.execvp("sudo", ["sudo"] + python + sys.argv)
    # 3) populate the real parser and add information arguments
    __parsers = {}
    __get_calls_from_parser(parser, glob['parser'])
    if add['config']:
        c = p.add_argument_group(gt("config arguments"))
        opt = c.add_argument("-r", "--read-config", action='config',
                             help=gt("read args from a config file"),
                             note=gt("this overrides other arguments"))
        c.add_argument("-w", "--write-config", metavar="INI",
                       help=gt("write args to a config file"))
        if noarg and noargs_action == "config":
            sys.argv[1:] = [opt, "config.ini"]
    i = p.add_argument_group(gt("extra arguments"))
    if add['demo']:
        opt = i.add_argument("-d", "--demo", action='demo', prefix="play",
                             help=gt("demonstrate a random example"))
        if noarg and noargs_action == "demo":
            sys.argv[1:] = [opt]
    if add['help']:
        opt = i.add_argument("-h", "--help", action='help', prefix="show",
                             help=gt("show this help message and exit"))
        if noarg and noargs_action == "help":
            sys.argv[1:] = [opt]
    if add['step']:
        opt = i.add_argument("-s", "--step", action="store_true", last=True,
                             suffix="mode", help=gt("stepping mode"))
        if noarg and noargs_action == "step":
            sys.argv[1:] = [opt]
    if add['version']:
        version = glob['__version__'] if '__version__' in glob else None
        assert version, "__version__ is not defined"
        opt = i.add_argument("-v", "--version", action='version',
                             default=SUPPRESS, prefix="show", version=version,
                             help=gt("show program's version number and exit"))
        if noarg and noargs_action == "version":
            sys.argv[1:] = [opt]
    if multi_debug_level:
        i.add_argument("-v", dest="verbose", default=0, action="count",
                       suffix="mode",  cancel=True, last=True,
                       help=gt("verbose level"),
                       note=gt("-vvv corresponds to the highest verbose level"))
    else:
        i.add_argument("-v", "--verbose", action="store_true", last=True,
                       suffix="mode", help=gt("verbose mode"))
    if add['wizard']:
        opt = i.add_argument("-w", "--wizard", action='wizard', default=SUPPRESS,
                             prefix="start", help=gt("start a wizard"))
        if noarg and noargs_action == "wizard":
            sys.argv[1:] = [opt]
    if report_func is not None:
        if not isfunction(report_func):
            glob['logger'].error("Bad report generation function")
            return
        r = glob['parser'].add_argument_group(gt("report arguments"))
        choices = map(lambda x: x[0],
                      filter(lambda x: not x[0].startswith('_'),
                             getmembers(Report, predicate=ismethod)))
        if r.add_argument("--output", choices=choices, default="pdf", last=True,
                          prefix="report", help=gt("report output format")):
            r.add_argument("--title", last=True, prefix="report",
                           help=gt("report title"))
            r.add_argument("--css", last=True, prefix="report",
                           help=gt("report stylesheet file"))
            r.add_argument("--theme", default="default", last=True,
                           prefix="report", help=gt("report stylesheet theme"),
                           note=gt("--css overrides this setting"))
            r.add_argument("--filename", last=True, prefix="report",
                           help=gt("report filename"))
    glob['args'] = glob['parser'].parse_args()
    # 4) configure logging and get the main logger
    configure_logger(glob, multi_debug_level)
    # 5) append stepping mode items
    set_step_items(glob)
    # 6) finally, bind the global exit handler
    def __at_exit():
        # first, dump the config if required
        if add['config']:
            cf = glob['args'].write_config
            if cf:
                with open(cf, 'w') as f:
                    glob['parser']._config.write(f)
                glob['logger'].debug("Input arguments written to file "
                                     "'{}'".format(cf))
        # then handle the state
        if _hooks.state == "INTERRUPTED":
            glob['at_interrupt']()
        elif _hooks.state == "TERMINATED":
            glob['at_terminate']()
        else:
            if report_func is not None:
                # generate the report only when exiting gracefully, just before
                #  the user-defined function at_graceful_exit
                _ = glob['args']
                r = Report(*report_func(), title=_.title, filename=_.filename,
                           logger=glob['logger'], css=_.css)
                getattr(r, _.output)(False)
            glob['at_graceful_exit']()
        glob['at_exit']()
        logging.shutdown()
    atexit.register(__at_exit)


def validate(glob, *arg_checks):
    """
    Function for validating group of arguments ; each argument is represented as
     a 4-tuple like follows:

        (argument_name, fail_condition, error_message, default)

        - argument_name: the name of the argument like entered in add_argument()
        - fail_condition: condition in Python code with the argument name
                          replaced by ' ? ' (e.g. " ? > 0")
        - error_message: message describing what failed with the validation ofs
                         the current argument
        - default [optional]: value to be given if the validation fails ; this
                              implies that the script will not exit after the
                              validation (if no other blocking argument present)

    :param glob:       globals() instance from the calling script
    :param arg_checks: list of 3/4-tuples
    """
    locals().update(glob)  # allows to import user-defined objects from glob
                           #  into the local scope
    if glob['args'] is None or glob['logger'] is None:
        return
    exit_app = False
    for check in arg_checks:
        check = check + (None, ) * (4 - len(check))
        param, condition, message, default = check
        assert re.match(r'^_?[a-zA-Z][a-zA-Z0-9_]*$', param) is not None, \
               "Illegal argument name"
        try:
            result = eval(condition.replace(" ? ", " glob['args'].{} "
                                            .format(param)))
        except (AssertionError, TypeError) as e:
            result = True
            message = str(e)
        if result:
            if default is None:
                glob['logger'].error(message or "Validation failed")
                exit_app = True
            else:
                glob['logger'].warn(message or "Validation failed")
                setattr(glob['args'], param, default)
    if exit_app:
        sys.exit(2)


class ProxyArgumentParser(object):
    """
    Proxy class for collecting added arguments before initialization.
    """
    def __init__(self):
        self.calls = []
        self.__parser = ArgumentParser()

    def __getattr__(self, name):
        self.__current_call = name
        self.__call_exists = hasattr(self.__parser, name) and \
                             callable(getattr(self.__parser, name))
        return self.__collect

    def __collect(self, *args, **kwargs):
        subparser = ProxyArgumentParser()
        self.calls.append((self.__current_call, self.__call_exists,
                           args, kwargs, subparser))
        del self.__current_call
        del self.__call_exists
        return subparser


parser = ProxyArgumentParser()
