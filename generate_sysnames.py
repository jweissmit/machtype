#!/usr/bin/python
#
# Attempt to generate the sysname and compat list for this
# architecture and distribution.  Print the sysname and
# a colon-separated syscompat list to stdout.

from collections import defaultdict
import itertools
import os
import re
import subprocess
import sys

# Default architectures, if not specified in the distro definition
DEFAULT_ARCHES = ('i386', 'amd64')

# A dictionary mapping an architecture to a list of architectures
# it is compatible with
COMPAT_ARCHES = defaultdict(list,
                            {'amd64': ['i386'],
                             })

def fail(*args):
    """Exit and display an error gracefully"""
    for a in args:
        print >>sys.stderr, os.path.basename(sys.argv[0]) + ':', a
    sys.exit(1)

def run(*args):
    """Run a command and its arguments and return the output or fail"""
    try:
        return subprocess.check_output(args,
                                       shell=False,
                                       stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as e:
        fail("Command failed: ", args, "Output:", e.output)

IS_UBUNTU = os.getenv('OVERRIDE_MACHTYPE_LSB_ID',
                      run('lsb_release', '--short','--id')).lower() == "ubuntu"
DEBIAN_VERSION = os.getenv('OVERRIDE_MACHTYPE_DEB_VERSION',
                           run('dpkg-query',
                               '--showformat=${Version}',
                               '--show',
                               'base-files'))
UBUNTU_VERSION = os.getenv('OVERRIDE_MACHTYPE_UBUNTU_VERSION',
                           run('lsb_release',
                               '--short',
                               '--release'))
ARCH = os.getenv('OVERRIDE_MACHTYPE_ARCH',
                 run('dpkg-architecture',
                     '-qDEB_BUILD_ARCH'))

MAX_SYSNAMES = 32

# If you use unicode version strings, I hate you
digits = re.compile("[^0-9]")

def archlist(arch):
    return [arch] + COMPAT_ARCHES[arch]

def compare_versions(ver1, op, ver2):
    assert ver1 is not None and ver2 is not None and \
        op in ('lt', 'le', 'eq', 'ne', 'ge', 'gt')
    return subprocess.call(['dpkg', '--compare-versions',
                            ver1, op, ver2], shell=False) == 0

class Distro(object):
    def __init__(self, version, **kwargs):
        self.version = version
        self.vercmp = os.uname()[2]
        self.arches = kwargs.get('arches', DEFAULT_ARCHES)
        self.sysver = digits.sub('', kwargs.get('sysver', version))
        self.sysprefix = kwargs.get('sysprefix', 'linux')

    def suitable(self):
        if ARCH not in self.arches:
            return False
        if not compare_versions(self.vercmp, 'ge', self.version):
            return False
        if not IS_UBUNTU and isinstance(self, Ubuntu):
            return False
        return True

    def sysnames(self):
        rv = []
        for a in archlist(ARCH):
            if a in self.arches:
                rv.append("{a}_{d}{v}".format(a=a,
                                              d=self.sysprefix,
                                              v=self.sysver))
        return rv

class Debian(Distro):
    def __init__(self, version, **kwargs):
        assert 'sysprefix' not in kwargs
        super(Debian, self).__init__(version, sysprefix='deb', **kwargs)
        self.vercmp = DEBIAN_VERSION

class Ubuntu(Distro):
    def __init__(self, version, **kwargs):
        assert 'sysprefix' not in kwargs
        super(Ubuntu, self).__init__(version, sysprefix='ubuntu', **kwargs)
        self.vercmp = UBUNTU_VERSION

# The master distro order
# Update this when a new release comes online
distros = [Ubuntu('14.04'),
           Ubuntu('13.10'), Ubuntu('13.04'),
           Debian('7.0', arches=DEFAULT_ARCHES + ('armel',)),
           Ubuntu('12.10'), Ubuntu('12.04'),
           Debian('6.0'),
           Ubuntu('11.10'), Ubuntu('11.04'),
           Ubuntu('10.10'), Ubuntu('10.04'),
           Ubuntu('9.04'),
           Debian('4.0.4', sysver='5.0'),
           Ubuntu('8.04'),
           Debian('4.0')]

print >>sys.stderr, "Using values: Debian: {0}, {1}, Arch: {2}".format(
    DEBIAN_VERSION,
    "Ubuntu: {0}".format(UBUNTU_VERSION) if IS_UBUNTU else "(not Ubuntu)",
    ARCH)

if not compare_versions(DEBIAN_VERSION, 'ge', '3.1'):
    fail("Go find an operating system released in 2008 or later.")

sysnames = list(
    itertools.chain(*[d.sysnames() for d in distros if d.suitable()]))

if len(sysnames) < len(archlist(ARCH)):
    fail("Insufficient number of sysnames, cannot proceed.",
         "sysnames: {0}".format(sysnames))

sysname = sysnames.pop(0)
sysnames += ['i386_rhel4']

if not compare_versions(DEBIAN_VERSION, 'ge', '7.0'):
    sysnames += ['i386_rhel3', 'i386_linux24']

if len(sysnames) + 1 > MAX_SYSNAMES:
    fail("Sysname list too long")

if IS_UBUNTU and (Ubuntu(UBUNTU_VERSION).sysnames()[0] != sysname):
    fail("Sysname mismatch -- is this a new release?",
         "{0} != {1}".format(Ubuntu(UBUNTU_VERSION).sysnames()[0], sysname))
elif not IS_UBUNTU:
    # We only compare major versions.  This is a hack.
    deb_ver_compare = "{0:.1f}".format(int(DEBIAN_VERSION.split('.')[0]))
    if Debian(deb_ver_compare).sysnames()[0] != sysname:
        fail("Sysname mismatch -- is this a new release?",
             "{0} != {1}".format(Debian(deb_ver_compare).sysnames()[0],
                                 sysname))

print "{sysname} {syscompat}".format(
    sysname=sysname.strip(),
    syscompat=':'.join([x.strip() for x in sysnames]))
sys.exit(0)
