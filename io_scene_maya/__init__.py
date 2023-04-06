bl_info = {
    "name": "Import Maya Scene (.ma)",
    "author": "Richard Brenick",
    "version": (1, 0),
    "blender": (3, 3, 0),
    "location": "File - Import",
    "description": "Import some of the content from a maya scene file",
    "warning": "Don't expect magic. At best you'll get some geometry. As a treat.",
    "doc_url": "",
    "category": "Import-Export",
}

import os
import bpy
from bpy.props import (
        StringProperty,
        CollectionProperty,
        )

from bpy_extras.io_utils import (
    ImportHelper,
    orientation_helper,
    axis_conversion,
)


@orientation_helper(axis_forward='-Z', axis_up='Y')
class ImportMA(bpy.types.Operator, ImportHelper):
    """Load a Autodesk Maya .ma File"""
    bl_idname = "import_scene.maya_ascii"
    bl_label = "Import Maya ASCII Scene"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".ma"
    filter_glob: StringProperty(
        default="*.ma",
        options={'HIDDEN'},
    )
    
    # Selected files
    files: CollectionProperty(type=bpy.types.PropertyGroup)

    def execute(self, context):
        from . import maya_scene_importer

        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "filter_glob",
                                            ))

        global_matrix = axis_conversion(
            from_forward=self.axis_forward,
            from_up=self.axis_up,
        ).to_4x4()
        
        keywords["correction_matrix"] = global_matrix

        if bpy.data.is_saved and context.user_preferences.filepaths.use_relative_paths:
            keywords["relpath"] = os.path.dirname((bpy.data.path_resolve("filepath", False).as_bytes()))
        
        folder = os.path.dirname(self.filepath)
        
        failed_files = []
        for file in self.files:
            file_path = os.path.join(folder, file.name)
            
            keywords["filepath"] = file_path
            res = maya_scene_importer.import_scene(self, context, **keywords)
            
            if res != {"FINISHED"}:
                failed_files.append(res)
        
        if failed_files:
            return {"CANCELLED"}
        
        return {"FINISHED"}


def menu_func_import(self, context):
    self.layout.operator(ImportMA.bl_idname, text="Maya ASCII Scene (.ma)")


classes = (
    ImportMA,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
