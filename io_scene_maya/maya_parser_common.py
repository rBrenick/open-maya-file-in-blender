import struct


def be_word4(buf):
    return struct.unpack('>L', buf)[0]


def le_word4(buf):
    return struct.unpack('<L', buf)[0]


def be_word8(buf):
    return struct.unpack('>Q', buf)[0]


def le_word8(buf):
    return struct.unpack('<Q', buf)[0]


def be_read4(stream):
    return struct.unpack('>L', stream.read(4))[0]


def le_read4(stream):
    return struct.unpack('<L', stream.read(4))[0]


def be_read8(stream):
    return struct.unpack('>Q', stream.read(8))[0]


def le_read8(stream):
    return struct.unpack('<Q', stream.read(8))[0]


def align(size, stride):
    return stride * int(1 + ((size - 1) / stride))


def read_null_terminated(stream):
    result = b''
    next = stream.read(1)
    while stream and next != b'\0':
        result += next
        next = stream.read(1)
    return result


def plug_element_count(plug):
    lbracket = plug.rfind(b'[')
    if lbracket != -1:
        rbracket = plug.rfind(b']')
        if rbracket != -1 and lbracket < rbracket:
            slicestr = plug[lbracket + 1:rbracket]
            bounds = slicestr.split(b':')
            if len(bounds) > 1:
                return int(bounds[1]) - int(bounds[0]) + 1
    return 1


class MayaParserBase(object):

    def on_requires_maya(self, version):
        pass

    def on_requires_plugin(self, plugin, version):
        pass

    def on_file_info(self, key, value):
        pass

    def on_current_unit(self, angle, linear, time):
        pass

    def on_file_reference(self, path):
        pass

    def on_create_node(self, nodetype, name, parent):
        pass

    def on_select(self, name):
        pass

    def on_add_attr(self, node, name):
        pass

    def on_set_attr(self, name, value, type):
        pass

    def on_set_attr_flags(self, plug, keyable=None, channelbox=None, lock=None):
        pass

    def on_connect_attr(self, src_plug, dst_plug):
        pass
