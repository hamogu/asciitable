"""Asciitable: an extensible ASCII table reader and writer.

daophot.py:
  Classes to read DAOphot table format

:Copyright: Smithsonian Astrophysical Observatory (2011)
:Author: Tom Aldcroft (aldcroft@head.cfa.harvard.edu)
"""

## 
## Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are met:
##     * Redistributions of source code must retain the above copyright
##       notice, this list of conditions and the following disclaimer.
##     * Redistributions in binary form must reproduce the above copyright
##       notice, this list of conditions and the following disclaimer in the
##       documentation and/or other materials provided with the distribution.
##     * Neither the name of the Smithsonian Astrophysical Observatory nor the
##       names of its contributors may be used to endorse or promote products
##       derived from this software without specific prior written permission.
## 
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
## ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
## WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
## DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
## DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
## (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
## LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
## ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
## (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS  
## SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import re
import asciitable.core as core
import asciitable.basic as basic
import asciitable.fixedwidth as fixedwidth

class Daophot(core.BaseReader):
    """Read a DAOphot file.
    Example::

      #K MERGERAD   = INDEF                   scaleunit  %-23.7g  
      #K IRAF = NOAO/IRAFV2.10EXPORT version %-23s
      #K USER = davis name %-23s
      #K HOST = tucana computer %-23s
      #
      #N ID    XCENTER   YCENTER   MAG         MERR          MSKY           NITER    \\
      #U ##    pixels    pixels    magnitudes  magnitudes    counts         ##       \\
      #F %-9d  %-10.3f   %-10.3f   %-12.3f     %-14.3f       %-15.7g        %-6d     
      #
      #N         SHARPNESS   CHI         PIER  PERROR                                \\
      #U         ##          ##          ##    perrors                               \\
      #F         %-23.3f     %-12.3f     %-6d  %-13s
      #
      14       138.538   256.405   15.461      0.003         34.85955       4        \\
      -0.032      0.802       0     No_error

    The keywords defined in the #K records are available via the Daophot reader object::

      reader = asciitable.get_reader(Reader=asciitable.DaophotReader)
      data = reader.read('t/daophot.dat')
      for keyword in reader.keywords:
          print keyword.name, keyword.value, keyword.units, keyword.format
    
    """
    
    def __init__(self):
        core.BaseReader.__init__(self)
        self.header = DaophotHeader()
        self.inputter = core.ContinuationLinesInputter()
        self.data.splitter = fixedwidth.FixedWidthSplitter()
        #self.data.splitter.replace_char = ' '
        self.data.start_line = 0
        self.data.comment = r'\s*#'
    
    def read(self, table):
        output = core.BaseReader.read(self, table)
        if core.has_numpy:
            reader = core._get_reader(Reader=basic.NoHeaderReader, comment=r'(?!#K)', 
                                      names = ['temp1','keyword','temp2','value','unit','format'])
            headerkeywords = reader.read(self.comment_lines)

            for line in headerkeywords:
                self.keywords.append(core.Keyword(line['keyword'], line['value'], 
                                                  units=line['unit'], format=line['format']))
        self.table = output
        self.cols = self.header.cols

        return self.table

    def write(self, table=None):
        raise NotImplementedError

DaophotReader = Daophot

class DaophotHeader(core.BaseHeader):
    """Read the header from a file produced by the IRAF DAOphot routine."""
    def __init__(self):
        core.BaseHeader.__init__(self)
        self.comment = r'\s*#K'

    def get_cols(self, lines):
        """Initialize the header Column objects from the table ``lines`` for a DAOphot
        header.  The DAOphot header is specialized so that we just copy the entire BaseHeader
        get_cols routine and modify as needed.

        :param lines: list of table lines
        :returns: list of table Columns
        """

        self.names = []
        col_width = []
        re_name_def = re.compile(r'#N([^#]+)#')
        re_colformat_def = re.compile(r'#F([^#]+)')
        col_len_def = re.compile(r'[0-9]+')
        for line in lines:
            if not line.startswith('#'):
                break                   # End of header lines
            else:
                match = re_name_def.search(line)
                formatmatch = re_colformat_def.search(line)
                if match:
                    self.names.extend(match.group(1).split())
                if formatmatch:
                    form = formatmatch.group(1).split()
                    width = ([int(col_len_def.search(s).group()) for s in form])
                    # original data format might be shorter than 80 characters
                    # and filled with spaces
                    width[-1] = 80 - sum(width[:-1])
                    col_width.extend(width)
        
        if not self.names:
            raise core.InconsistentTableError('No column names found in DAOphot header')
        
        starts = [int(sum(col_width[0:i])) for i in range(len(col_width))]
        ends = [col_width[i] + starts[i] for i in range(len(col_width))]

        # Filter self.names using include_names and exclude_names, then create
        # the actual Column objects.
        self._set_cols_from_names()
        self.n_data_cols = len(self.cols)
        
        # Set column start and end positions.  Also re-index the cols because
        # the FixedWidthSplitter does NOT return the ignored cols (as is the
        # case for typical delimiter-based splitters)
        for i, col in enumerate(self.cols):
            col.start = starts[col.index]
            col.end = ends[col.index]
            col.index = i