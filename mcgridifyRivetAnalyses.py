#! /usr/bin/env python
"""This script prepares existing Rivet analyses for use with MCgrid.

- The prefix 'MCgrid_' is added to the analysis name.
- An include statement for MCgrid is added to the analysis source file.

Have a look at "https://rivet.hepforge.org/analyses" for a list of analyses.

The output analysis files will be saved in the current working directory.
They are named as follows: "MCgrid_ORIGINAL_ANALYSIS_NAME" plus their file
extensions.
"""

import argparse
import tempfile
import shutil
import os
import urllib
import urlparse
import fileinput
import sys
import re

import time

anainfo_key = 'anainfo'
plotinfo_key = 'plotinfo'
refdata_key = 'refdata'
source_key = 'source'
keys = anainfo_key, plotinfo_key, refdata_key, source_key


def make_temporary_directory():
    return tempfile.mkdtemp()


def remove_temporary_directory(dtemp):
    shutil.rmtree(dtemp)


class InfectAnalysisException(Exception):
    pass


class CannotLocateFileException(InfectAnalysisException):
    pass


class DownloadFailureException(InfectAnalysisException):
    pass


class DownloadNotFoundException(DownloadFailureException):
    pass

class ParseMemberGroupException(InfectAnalysisException):
    pass

class ParseMethodException(InfectAnalysisException):
    pass


class AnalysisFileCollector:
    _extensions = {
        anainfo_key: ('info', ),
        plotinfo_key: ('plot', ),
        refdata_key: ('yoda', ),
        source_key: ('cc', 'c', 'cpp', 'cxx')}
    def __init__(self, analysis, target_dir=os.getcwd()):
        self._analysis = analysis
        self._target_dir = target_dir
    def collect_files(self):
        file_collection = {}
        for key in keys:
            try:
                file_path = self.collect_file(key)
            except (CannotLocateFileException, DownloadNotFoundException):
                if (key == refdata_key):
                    print("No reference data has been found for this"
                          + " analysis.")
                else:
                    raise
            else:
                file_collection[key] = file_path
        return file_collection
    def collect_file(self, key):
        # Concrete subclasses have to overwrite this method
        return None
    def file_names(self, key, only_preferred=False):
        extensions = self._extensions[key]
        if only_preferred:
            return self._analysis + '.' + extensions[0]
        file_names = []
        for extension in self._extensions[key]:
            file_names.append(self._analysis + '.' + extension)
        return file_names
    def target_file_path(self, file_name):
        return os.path.join(self._target_dir, file_name)


class AnalysisLocalFileCopier(AnalysisFileCollector):
    _default_sub_dirs = {
        anainfo_key: 'anainfo/',
        plotinfo_key: 'plotinfo/',
        refdata_key: 'refdata/',
        source_key: None}
    def __init__(self,
                 analysis,
                 target_dir=None,
                 data_dir=os.getcwd(),
                 source_dir=os.getcwd()):
        AnalysisFileCollector.__init__(self, analysis, target_dir=target_dir)
        self._data_dir=data_dir
        self._source_dir=source_dir
    def collect_file(self, key):
        return self.copy_file(key)
    def copy_file(self, key):
        if key in (anainfo_key,
                   plotinfo_key,
                   refdata_key):
            source_dir = self._data_dir
        else:
            source_dir = self._source_dir

        candidate_file_names = self.file_names(key)
        candidate_dirs = [source_dir]
        sub_dir = self._default_sub_dirs[key]
        if sub_dir is not None:
            candidate_dirs.append(os.path.join(source_dir, sub_dir, ))
        directory, file_name = self.locate_file(candidate_dirs,
                                                candidate_file_names)

        path = os.path.join(directory, file_name)
        shutil.copy2(path, self._target_dir)
        return self.target_file_path(file_name)

    def locate_file(self, candidate_dirs, candidate_file_names):
        for candidate_dir in candidate_dirs:
            for candidate_file_name in candidate_file_names:
                candidate_path = os.path.join(candidate_dir,
                                              candidate_file_name)
                if os.path.isfile(candidate_path):
                    return candidate_dir, candidate_file_name
        raise CannotLocateFileException(
            "There was no local file named\n\n    "
            + candidate_file_names
            + "\n\n at the directories\n\n    "
            + candidate_dirs + ".")

class AnalysisFileDownloader(AnalysisFileCollector):

    _expected_types = {
        anainfo_key: 'application/x-info',
        plotinfo_key: 'text/plain',
        refdata_key: 'text/plain',
        source_key: 'text/x-c++src'}
    _expected_failure_type = 'text/html'  # 'failure' means the Tracker did not 
                                          # find the file and therefore
                                          # returned a failure web page to us

    def __init__(self,
                 analysis,
                 target_dir=None,
                 commit_id='HEAD',
                 data_dir=os.getcwd(),
                 source_dir=os.getcwd()):
        AnalysisFileCollector.__init__(self, analysis, target_dir=target_dir)
        self._data_dir=data_dir
        self._source_dir=source_dir
        base_url = 'https://rivet.hepforge.org/trac/export/' + commit_id + '/'
        data_url = base_url + 'data/'
        self._dir_urls = {
            anainfo_key:  data_url + 'anainfo/',
            plotinfo_key: data_url + 'plotinfo/',
            refdata_key:  data_url + 'refdata/',
            source_key:   base_url + 'src/Analyses/'}                                      

    def collect_file(self, key):
        return self.download_file(key)

    def _file_url(self, key):
        return self._dir_urls[key] + self.file_names(key, only_preferred=True)

    def download_file(self, key):
        target_file_name = self.file_names(key, only_preferred=True)
        target_file_path = self.target_file_path(target_file_name)
        headers = urllib.urlretrieve(self._file_url(key),
                                     target_file_path)[1]
        if headers.gettype() != self._expected_types[key]:
            if headers.gettype() == self._expected_failure_type:
                raise DownloadNotFoundException(
                    'Downloading\n\n'
                    + '    ' + self._file_url(key)
                    + '\n\nfailed. Probably the file is not available.'
                    + '\nDo you have a typo in your analysis name(s)?'
                    + '\nOpen the URL in your browser for more details.')
            else:
                raise DownloadFailureException(
                    'Downloading\n\n'
                    + '    ' + self._file_url(key)
                    + '\n\nfailed for an unknown reason. Sorry.')
        return target_file_path


parser = argparse.ArgumentParser(description=__doc__)

# Positional argument for specifying analyses (at least one)
parser.add_argument('analyses', nargs='+', metavar='analysis',
                    help='Give at least one analysis name'
                    + ' (without a file extension)'
                    + ', e.g. "MC_DIJET".')

rivet_remote_subdirectories={'2.2.0': '96aa6bd1c36a0891fb6a620919920090505466ef',
                             '2.2.1': '805d410d6fadd4efb8d0e6bdf5a930ec0fc1e848',
                             '2.3.0': '086c7cd50a1906839b8440845077a39a0279ebb0',
                             'HEAD' : 'HEAD'}
remote_arguments = parser.add_argument_group('remote file infection')
remote_arguments.add_argument('-v', '--rivet-version',
                              default='2.3.0',
                              choices=sorted(rivet_remote_subdirectories.keys()),
                              help='The rivet version for which to download'
                              + ' and infect the analyses.')

# Arguments for infecting local files
local_arguments = parser.add_argument_group('local file infection')
local_arguments.add_argument('-l', '--local', action='store_true',
                             help='Use this flag to infect a Rivet analysis'
                             + ' which is stored locally.'
                             + ' Otherwise the files will be downloaded'
                             + ' from "https://rivet.hepforge.org".')
local_arguments.add_argument('-c', '--source-path',
                             default=os.getcwd(),
                             help='The Rivet analysis source file is assumed'
                             + ' to exist at SOURCE_PATH.'
                             + ' The file name has to be the same'
                             + ' as the given analysis name.'
                             + ' The extension can be ".cc", ".c",'
                             + ' ".cpp" or ".cxx".'
                             + ' The default is the current working directory.'
                             + ' SOURCE_PATH is ignored'
                             + ' unless --local is used.')
local_arguments.add_argument('-d', '--data-path',
                             default=os.getcwd(),
                             help='Rivet analyses come with'
                             + ' an analysis info file (".info")'
                             + ', a plot info (".plot")'
                             + ' and an optional reference data file'
                             + ' (".yoda").'
                             + ' These files are assumed to exist'
                             + ' either at DATA_PATH'
                             + ', or in subdirectories respectively called'
                             + ' "anainfo", "plotinfo" and "refdata".'
                             + ' The default is the current working directory.'
                             + ' DATA_PATH is ignored'
                             + ' unless --local is used.')

args = parser.parse_args()


# Create a temporary directory
dtemp = make_temporary_directory()
# print(dtemp)

try:
    for analysis in args.analyses:
        # Copy or download analyses files
        if args.local:
            file_collector = AnalysisLocalFileCopier(
                analysis,
                target_dir=dtemp,
                data_dir=args.data_path,
                source_dir=args.source_path)
        else:
            commit_id = rivet_remote_subdirectories[args.rivet_version]
            file_collector = AnalysisFileDownloader(analysis, target_dir=dtemp, commit_id=commit_id)
        file_collection = file_collector.collect_files()

        # Replace every occurrence of the analysis name with our modified one 
        for line in fileinput.input(files=file_collection.values(), inplace=1):
            sys.stdout.write(line.replace(analysis, "MCgrid_" + analysis))

        # Read in the source file
        with open (file_collection[source_key], 'r') as f:
            source = f.read()

        # Where to split the source string and what to insert there in
        # the form: (pos, insertion)
        insertions = []

        # Insert include line
        index = source.rindex('#include')
        bol_index = source.rindex("\n", 0, index) + 1
        eol_index = source.index("\n", index)
        whitespace = source[bol_index:index]
        insertion = "\n" + whitespace + '#include "mcgrid/mcgrid.hh"'
        insertions.append((eol_index, insertion))

        slices = []
        last_pos = 0
        for pos, insertion in insertions:
            slices.append(source[last_pos:pos])
            slices.append(insertion)
            last_pos = pos
        slices.append(source[last_pos:])

        # Write the modified source file
        with open(file_collection[source_key], 'w') as f:
            for slice in slices:
                f.write(slice)

        # Move modified files into current working directory
        for file in file_collection.values():
            os.rename(file, 'MCgrid_' + os.path.basename(file))

finally:
    remove_temporary_directory(dtemp)
