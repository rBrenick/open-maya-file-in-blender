"""

This file originates from https://github.com/mottosso/maya-scenefile-parser
which is a branch of https://github.com/agibli/sansapp

I re-wrote the _exec_set_attr handling, but otherwise mostly unchanged


Here's the license info from the original repo
--------------------------

Copyright (c) 2016 Alon Gibli

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import json

from . import maya_parser_common as common


class MayaAsciiError(ValueError):
    pass


class MayaAsciiParserBase(common.MayaParserBase):
    def __init__(self):
        self.__command_handlers = {
            "requires": self._exec_requires,
            "fileInfo": self._exec_file_info,
            "file": self._exec_file,
            "createNode": self._exec_create_node,
            "setAttr": self._exec_set_attr,
        }

    def on_comment(self, value):
        pass

    def register_handler(self, command, handler):
        self.__command_handlers[command] = handler

    def exec_command(self, command, args):
        handler = self.__command_handlers.get(command, None)
        if handler is not None:
            handler(args)

    def has_command(self, command):
        return command in self.__command_handlers

    def _exec_requires(self, args):
        if args[0] == "maya":
            self.on_requires_maya(args[1])
        else:
            self.on_requires_plugin(args[0], args[1])

    def _exec_file_info(self, args):
        self.on_file_info(args[0], args[1])

    def _exec_file(self, args):
        reference = False
        reference_depth_info = None
        namespace = None
        defer_reference = False
        reference_node = None

        argptr = 0
        while argptr < len(args):
            arg = args[argptr]
            if arg in ("-r", "--reference"):
                reference = True
                argptr += 1
            elif arg in ("-rdi", "--referenceDepthInfo"):
                reference_depth_info = int(args[argptr + 1])
                argptr += 2
            elif arg in ("-ns", "--namespace"):
                namespace = args[argptr + 1]
                argptr += 2
            elif arg in ("-dr", "--deferReference"):
                defer_reference = bool(int(args[argptr + 1]))
                argptr += 2
            elif arg in ("-rfn", "--referenceNode"):
                reference_node = args[argptr + 1]
                argptr += 2
            elif arg in ('-op'):
                argptr += 2
            else:
                break

        if argptr < len(args):
            path = args[argptr]
            self.on_file_reference(path)

    def _exec_create_node(self, args):
        nodetype = args[0]

        name = None
        parent = None

        argptr = 1
        while argptr < len(args):
            arg = args[argptr]
            if arg in ("-n", "--name", "-name"):
                name = args[argptr + 1]
                argptr += 2
            elif arg in ("-p", "--parent", "-parent"):
                parent = args[argptr + 1]
                argptr += 2
            elif arg in ("-s", "--shared", "-shared"):
                argptr += 1
            else:
                raise MayaAsciiError("Unexpected argument: %s" % arg)

        self.on_create_node(nodetype, name, parent)

    def _exec_set_attr(self, args):
        """
        this is the biggest difference from https://github.com/mottosso/maya-scenefile-parser
        pretty much entirely re-written
        
        some example of commands that need to be handled
        
        setAttr -k off ".v";
        setAttr -s 10 ".iog[0].og";
        setAttr ".cuvs" -type "string" "map1";
        setAttr ".dcc" -type "string" "Ambient+Diffuse";
        setAttr ".covm[0]"  0 1 1;
        setAttr ".cdvm[0]"  0 1 1;
        setAttr ".sdt" 0;
        setAttr ".ugsdt" no;
        setAttr ".uvst[0].uvsn" -type "string" "map1";
        setAttr -s 146 ".uvst[0].uvsp[0:145]" -type "float2" 0.459
        setAttr -s 5323 -ch 15969 ".fc";
        """
        
        name = None  # attribute_name
        attrtype = None
        data_index_start = 0
        
        skip_next_arg = False
        for arg in args:
            
            if skip_next_arg:
                data_index_start += 1
                skip_next_arg = False
                continue
            
            # unless a special case comes up, the values should start on this index
            data_has_started = True
            
            # the first arg with a dot should be the attr name
            if '.' in arg and name is None:
                name = arg
                data_has_started = False
                
            # deal with setAttr args
            # might be safer to list all setAttr arguments, since "-" can show up elsewhere
            if "-" in arg and arg.strip("-").isalpha():
                data_has_started = False
                
                if arg in ("-type", "--type"):
                    attrtype = args[data_index_start + 1]
                
                # alteredValue doesn't have any arguments apparently
                if not "-av" in arg:
                    skip_next_arg = True
            
            # break the loop so we don't have to iterate all the args
            if data_has_started:
                break
            
            # keep adding until we've dealt with everything non-data
            data_index_start += 1
        
        value = args[data_index_start:]
        
        # sometimes attrtype is set, sometimes it isn't, so there's some redundancy happening below
        if attrtype == "double3" or attrtype == "float3":
            value = [float(f) for f in value]
        
        if ".uvsp[" in name:
            float_converted = [float(f) for f in value]
            value = list(chunks(float_converted, 2))
            attrtype = "float2"
            
        elif ".pt[" in name and ":" in name:
            float_converted = [float(f) for f in value]
            value = list(chunks(float_converted, 3))
            attrtype = "double3Array"
        
        elif ".vt[" in name and not "vl" in name:
            float_converted = [float(f) for f in value]
            value = list(chunks(float_converted, 3))
            attrtype = "vtx" # not a real type, just for convenience
        
        elif ".ed[" in name:
            int_converted = [int(idx) for idx in value]
            value = list(chunks(int_converted, 3))
            attrtype = "edge" # not a real type, just for convenience
            
        # enforce polyFaces type for ".fc"
        elif ".fc[" in name:
            attrtype = "polyFaces"   
        
        """
        # it might be nice to skip the list when only a single value, but I'm not sure there's a safe way to go about it
        if len(value) == 1:
            if not isinstance(value[0], (list, tuple)):
                value = value[0]
        """
        self.on_set_attr(name, value, attrtype)
        

def chunks(in_list, size):
    for i in range(0, len(in_list), size):
        yield in_list[ i : i + size]

        
class MayaAsciiParser(MayaAsciiParserBase):

    def __init__(self, stream):
        super(MayaAsciiParser, self).__init__()
        self.__stream = stream

    def parse(self):
        while self.__parse_next_command():
            pass

    def __parse_next_command(self):
        lines = []

        line = self.__stream.readline()
        while True:
            # Check if we've reached the end of the file
            if not line:
                break

            # Handle comments
            elif line.startswith("//"):
                self.on_comment(line[2:].strip())

            # Handle commands
            # A command may span multiple lines
            else:
                line = line.rstrip("\r\n")
                if line and line.endswith(";"):
                    # Remove trailing semicolon here so the command line
                    # processor doesn't have to deal with it.
                    lines.append(line[:-1])
                    break
                elif line:
                    lines.append(line)
            line = self.__stream.readline()

        if lines:
            self.__parse_command_lines(lines)
            return True

        return False

    def __parse_command_lines(self, lines):
        # Pop command name from the first line
        command, _, lines[0] = lines[0].partition(" ")
        command = command.lstrip()

        # Only process arguments if we handle this command
        if self.has_command(command):

            # Tokenize arguments
            args = []
            for line in lines:
                while True:
                    line = line.strip()
                    if not line:
                        break

                    # Handle strings
                    if line[0] in "'\"":
                        string_delim = line[0]
                        escaped = False
                        string_end = len(line)

                        for i in range(1, len(line)):

                            # Check for end delimeter
                            if not escaped and line[i] == string_delim:
                                string_end = i
                                break

                            # Check for start of escape sequence
                            elif not escaped and line[i] == "\\":
                                escaped = True

                            # End escape sequence
                            else:
                                escaped = False

                        # Partition string argument from the remainder
                        # of the command line.
                        arg, line = line[1:string_end], line[string_end + 1:]

                    # Handle other arguments
                    # These, unlike strings, may be tokenized by whitespace
                    else:
                        arg, _, line = line.partition(" ")

                    args.append(arg)

            # Done tokenizing arguments, call command handler
            self.exec_command(command, args)

