"""
Copyright 2012 Lars Kruse <devel@sumpfralle.de>

This file is part of PyCAM.

PyCAM is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

PyCAM is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PyCAM.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import pycam.Exporters.GCode
from pycam.Toolpath import ToolpathPathMode
from pycam.workspace import LengthUnit


DEFAULT_DIGITS = 6


def _render_number(number):
    if int(number) == number:
        return "%d" % number
    else:
        return ("%%.%df" % DEFAULT_DIGITS) % number


class LinuxCNC(pycam.Exporters.GCode.BaseGenerator):
    is_rapid = False
    def add_header(self):
            self.add_command('G92 X0 Y0 Z0', comment='set to zero')

    def add_footer(self):
        pass

    def add_comment(self, comment):
        self.add_command("; %s" % comment)

    def add_command(self, command, comment=None):
        self.destination.write(command)
        if comment:
            self.destination.write("\t")
            self.add_comment(comment)
        else:
            self.destination.write(os.linesep)

    def add_move(self, coordinates, is_rapid=False):
        self.is_rapid = is_rapid
        components = []
        # the cached value may be:
        #   True: the last move was G0
        #   False: the last move was G1
        #   None: some non-move happened before
        components.append("G0" if is_rapid else "G1")
        axes = [axis for axis in "XYZABCUVW"]
        previous = self._get_cache("position", [None] * len(coordinates))
        for (axis, value, last) in zip(axes, coordinates, previous):
            if (last is None) or (last != value):
                components.append("%s%.6f" % (axis, value))
        command = " ".join(components)
        if command.strip():
            self.add_command(command)

    def command_feedrate(self, feedrate):
        if self.is_rapid:
            self.add_command("G0 F{}".format(_render_number(feedrate)), "set feedrate")
        else:
            self.add_command("G0 F{}".format(_render_number(feedrate)), "set feedrate")
    def command_select_tool(self, tool_id):
        pass

    def command_spindle_speed(self, speed):
        pass

    def command_spindle_enabled(self, state):
        pass

    def command_delay(self, seconds):
        # "seconds" may be floats or integers
        self.add_command("G4 P{}".format(seconds), "wait for {} seconds".format(seconds))

    def command_unit(self, unit):
        if unit == LengthUnit.METRIC_MM:
            self.add_command("G21", "metric")
        elif unit == LengthUnit.IMPERIAL_INCH:
            self.add_command("G20", "imperial")
        else:
            assert False, "Invalid unit requested: {}".format(unit)

    def command_corner_style(self, extra_args):
        pass
