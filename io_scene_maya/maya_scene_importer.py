import os
import sys
from math import radians
import mathutils
import bpy
from bpy_extras.io_utils import axis_conversion

from . import maya_parser_ascii

# convenience example call to this function
# import io_scene_maya.maya_scene_importer; import importlib; importlib.reload(io_scene_maya.maya_scene_importer); io_scene_maya.maya_scene_importer.import_scene(None, C, r"SOME_MAYA_FILE.ma")

def import_scene(operator, context, filepath, 
                 correction_matrix=None, 
                 *args, 
                 **kwargs
                 ):
    
    # nothing provided, assume it's a Y up maya scene
    if correction_matrix is None:
        correction_matrix = axis_conversion(
                        from_forward="-Z",
                        from_up="Y",
                        ).to_4x4()
    
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext != ".ma":
        if operator:
            operator.report({'ERROR'}, f"Only .ma files are supported, not: {os.path.basename(filepath)}")
        return {'CANCELLED'}
    
    print(f"Importing .ma: {filepath}")

    with open(filepath, "r") as f:
        parser = Parser(f)
        parser.correction_matrix = correction_matrix
        parser.parse()
        parser.build_scene()
        
    if operator:
        operator.report({'INFO'}, f"Imported: {os.path.basename(filepath)}")
    
    return {'FINISHED'}


class Parser(maya_parser_ascii.MayaAsciiParser):

    def __init__(self, *args, **kwargs):
        super(Parser, self).__init__(*args, **kwargs)
        
        self.on_supported_node = False
        self.current_node = None
        
        self.node_map = {}
        self.scene_nodes = []
        
        self.correction_matrix = None
    
    def on_create_node(self, nodetype, name, parent):
        
        # save previous node
        if self.current_node:
            # store both long and short name, since either may be referenced during loading
            self.node_map[self.current_node.name] = self.current_node
            self.node_map[self.current_node.long_name] = self.current_node
            self.scene_nodes.append(self.current_node)
            self.current_node = None
        
        self.on_supported_node = nodetype in (
            "mesh", 
            "transform", 
            "camera"
        )
        
        if not self.on_supported_node:
            return
        
        parent_node = self.node_map.get(parent)
        
        if nodetype == "mesh":
            self.current_node = Mesh(name, nodetype, parent_node)
            
        if nodetype == "transform":
            self.current_node = Transform(name, nodetype, parent_node)
            self.current_node.correction_matrix = self.correction_matrix
                              
        if nodetype == "camera":
            self.current_node = Camera(name, nodetype, parent_node)
            
        if parent_node is not None:
            parent_node.children.append(self.current_node)

    def on_set_attr(self, name, value, type):
        if not self.on_supported_node:
            return
        
        if name == ".t" and type == "double3":
            self.current_node.location = value
            return
        
        if name == ".r" and type == "double3":
            self.current_node.rotation = value
            return
        
        if name == ".s" and type == "double3":
            self.current_node.scale = value
            return
            
        if name == ".v":
            if value == ["no"]:
                self.current_node.visibility = False
            return

        # uv data
        if ".uvst" in name:
            if ".uvsn" in name:
                # get the number from .uvst[0]
                map_index = int(name.split("[")[1].split("]")[0])
                uv_data = self.current_node.uv_data.get(map_index, {})
                
                uv_data["name"] = value[0]
                self.current_node.uv_data[map_index] = uv_data
            
            if ".uvsp" in name and ":" in name:
                # get the first number from .uvst[0].uvsp[0:2]
                map_index = int(name.split("[")[1].split("]")[0])
                uv_data = self.current_node.uv_data.get(map_index, {})
                
                # get the last numbers from uvst[0].uvsp[0:2]
                start_index, end_index = name.split("[")[-1].split("]")[0].split(":")
                index_range = list(range(int(start_index), int(end_index)+1))
                
                # store all uv coordinate values, this is later indexed against polyFaces "mu"
                co_data = uv_data.get("co", {})
                for uv_idx, uv_coordinate in zip(index_range, value):
                    co_data[uv_idx] = uv_coordinate
                uv_data["co"] = co_data

                self.current_node.uv_data[map_index] = uv_data
            
            return
        
        if type == "vtx":
            # get the numbers from .vt[0:2]
            start_index, end_index = name.split("[")[1].split("]")[0].split(":")
            index_range = list(range(int(start_index), int(end_index) + 1))
            
            for vert_idx, vert_data in zip(index_range, value):
                self.current_node.vert_data[vert_idx] = vert_data
            
            return
        
        # point offsets I think this stands for?
        if "pt[" in name:
            if ":" in name:
                # get the numbers from .pt[0:2]
                start_index, end_index = name.split("[")[1].split("]")[0].split(":")
                index_range = list(range(int(start_index), int(end_index)+1))
                
                for vert_idx, subval in zip(index_range, value):
                    self.current_node.vert_offsets[vert_idx] = subval
            else:
                offset_index = int(name.split("[")[-1].split("]")[0])
                self.current_node.vert_offsets[offset_index] = value
                
            return
        
        if type == "edge":
            chunked_edges = []
            for val in value:
                chunked_edges.append((val[0], val[1])) # index 2 is hard/softness
            
            # get the numbers from .ed[0:2]
            start_index, end_index = name.split("[")[1].split("]")[0].split(":")
            index_range = list(range(int(start_index), int(end_index) + 1))
            
            for edge_idx, edge_connection in zip(index_range, chunked_edges):
                self.current_node.edge_data[edge_idx] = edge_connection
            
            return
        
        if type == "polyFaces":
            all_face_uv_data = self.current_node.face_uv_data
            
            all_raw_face_data = []
            for i, fv in enumerate(value):
                
                # get edge connection indices
                if fv == "f":
                    face_count = int(value[i+1])
                    
                    face_data = []
                    for j in range(face_count):
                        # skip first two indexes here, since that's just "f" and face_count
                        edge_index = int(value[i+2+j])
                        face_data.append(edge_index)
                    
                    all_raw_face_data.append(face_data)
                
                # get per-face uv indices
                if fv == "mu":
                    map_index = int(value[i+1])
                    face_count = int(value[i+2])
                    
                    uv_indices = []
                    for j in range(face_count):
                        # skip first three indexes here, since that's just mu, index, and face_count
                        uv_index = int(value[i+3+j])
                        uv_indices.append(uv_index)
                    
                    # store uv indices for each map index
                    map_data = all_face_uv_data.get(map_index, [])
                    map_data.append(uv_indices)
                    all_face_uv_data[map_index] = map_data
            
            
            # extract vertex id's from edge id's
            all_face_data = []
            for mesh_face in all_raw_face_data:
                face_data = []
                for edge_id in mesh_face:
                
                    # this took so goddamn long to figure out.
                    # edges[abs(id) - 1][1] to find vertices of a face
                    # autodesk what the fuu...?
                    if edge_id < 0:
                        target_vert = self.current_node.edge_data[abs(edge_id) - 1][1]
                    else:
                        target_vert = self.current_node.edge_data[edge_id][0]
                    
                    face_data.append(target_vert)
                
                all_face_data.append(face_data)
            
            self.current_node.face_data.extend(all_face_data)
            
            return
            
    def build_scene(self):
        for node in self.scene_nodes[:]:
        
            if len(node.children) == 1:
                if node.children[0].supports_single_parent:
                    # skip building parent transform when child can contain all the data, like camera or mesh
                    continue
            
            node.build()


class MayaNode(object):

    supports_single_parent = False
    
    def __init__(self, name, nodetype, parent):
        self.name = name
        self.nodetype = nodetype
        self.parent = parent
        self.children = []
        self.is_built = False
        
        self.visibility = True
        
        long_name = f"|{name}"
        if parent and isinstance(parent, MayaNode):
            long_name = f"{parent.long_name}{long_name}"
        self.long_name = long_name
    
    def build(self):
        pass


class Transform(MayaNode):
    def __init__(self, *args, **kwargs):
        super(Transform, self).__init__(*args, **kwargs)
        
        self.location = (0, 0, 0)
        self.rotation = (0, 0, 0)
        self.scale = (1, 1, 1)
        self.built_node = None
    
    def build(self, in_type=None):
        if self.is_built:
            return self.built_node
        
        self.is_built = True
        
        new_object = bpy.data.objects.new(self.name, in_type)
        bpy.context.scene.collection.objects.link(new_object)
        
        # save reference for transforms with multiple shape children
        self.built_node = new_object
        
        eul = mathutils.Euler(
            [
                radians(self.rotation[0]),
                radians(self.rotation[1]),
                radians(self.rotation[2]),
            ]
        )
        
        output_matrix = mathutils.Matrix.LocRotScale(self.location, eul, self.scale)

        if isinstance(self.parent, Transform):
            new_object.parent = self.parent.built_node
            new_object.matrix_basis = output_matrix
        else:
            # only apply axis correction on top level nodes
            new_object.matrix_basis = self.correction_matrix @ output_matrix
        
        if not self.visibility:
            new_object.hide_set(True)
        
        if isinstance(self.parent, Transform) and self.parent.visibility == False:
            self.visibility = False
            new_object.hide_set(True)
        
        return new_object


class Mesh(MayaNode):
    
    supports_single_parent = True
    
    def __init__(self, *args, **kwargs):
        super(Mesh, self).__init__(*args, **kwargs)
        
        self.vert_data = {}
        self.edge_data = {}
        self.face_data = []
        self.vert_offsets = {}
        
        self.uv_data = {}
        self.face_uv_data = {}
    
    def build(self):
        self.is_built = True
        
        if not self.vert_data:
            print(f"no vert data found to build mesh from: {self.name}")
            return
        
        # construct vertex list of from dict of indices
        final_verts = [(0,0,0)] * (max(self.vert_data.keys())+1)
        for idx, vtx_pos in self.vert_data.items():
        
            offset = self.vert_offsets.get(idx)
            if offset is not None:
                vtx_pos = (
                    vtx_pos[0] + offset[0],
                    vtx_pos[1] + offset[1],
                    vtx_pos[2] + offset[2],
                )
            
            final_verts[idx] = vtx_pos
        
        # construct edge list from dict of indices
        final_edges = [(0, 0)] * (max(self.edge_data.keys())+1)
        for idx, edge_connection in self.edge_data.items():
            final_edges[idx] = edge_connection
        
        new_mesh = bpy.data.meshes.new(self.name)
        new_mesh.from_pydata(final_verts, final_edges, self.face_data)
        new_mesh.validate(clean_customdata=False)
        new_mesh.update()
        
        # I wrote this in a haze, not sure I can explain it anymore, seems to work?
        for uv_set_index, uv_data in self.uv_data.items():
            uv_set_name = uv_data.get("name")
            coordinates = uv_data.get("co")
            new_uv = new_mesh.uv_layers.new(name=uv_set_name, do_init=False)
            
            if not coordinates:
                print(f"No uv data found on: {self.name} for set: {uv_set_name}")
                continue
            
            # build full list of uv coordinates that can be indexed per mesh.loop
            full_coordinates = []
            for face_index, face_uv_indices in enumerate(self.face_uv_data.get(uv_set_index)):
                for uv_index in face_uv_indices:
                    full_coordinates.append(coordinates[uv_index])
            
            for loop in new_mesh.loops:
                try:
                    new_uv.data[loop.index].uv = full_coordinates[loop.index]
                except IndexError:
                    print(f"{self.name} failed to map index '{loop.index}' to UVSet '{uv_set_name}' of length {len(full_coordinates)}, not sure why.")
                    continue
        
        obj = None
        
        # if the parent only has one child, and it's this, we can skip making an in-between transform
        if self.parent and len(self.parent.children) == 1:
            obj = self.parent.build(new_mesh)
            
        else:
            # parent needs multiple children, let's just add this mesh as a child
            obj = bpy.data.objects.new(self.name + "_TRANSFORM", new_mesh)
            bpy.context.scene.collection.objects.link(obj)
            
            if self.parent:
                obj.parent = self.parent.built_node
        
        # propagate visibilty
        if isinstance(self.parent, Transform) and self.parent.visibility == False:
            self.visibility = False
            obj.hide_set(True)
        

class Camera(MayaNode):
    
    supports_single_parent = True
    
    def __init__(self, *args, **kwargs):
        super(Camera, self).__init__(*args, **kwargs)

    def build(self):
        self.is_built = True
        
        new_camera = bpy.data.cameras.new(self.name)
        
        if len(self.parent.children) == 1:
            self.parent.build(new_camera)
        else:
            new_object = bpy.data.objects.new(self.name + "_TRANSFORM", new_camera)
            bpy.context.scene.collection.objects.link(new_object)
            new_object.parent = self.parent.built_node
