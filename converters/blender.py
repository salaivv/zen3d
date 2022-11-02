import sys
import bpy
from bpy import ops, data, context
from bpy.types import Material
from pprint import pprint


# sys.argv[6] is bake resolution
# sys.argb[7] is output GLB path

def requires_bake(material) -> bool:
    """
    Checks if a given material needs to be baked.

    Returns True if needs baking or False if otherwise.
    """
    is_transmission = False
    is_plain = True
    
    node_tree = material.node_tree

    node_material_output = None
    for node in node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL':
            node_material_output = node
            break
    
    node_principled = node_material_output.inputs["Surface"].links[0].from_node

    for i in node_principled.inputs:
        if len(i.links) > 0:
            is_plain = False
            break
    
    if node_principled.inputs["Transmission"].default_value > 0:
        is_transmission = True

    if is_plain:
        return False
    else:
        return True


def get_bake_materials() -> list[Material]:
    """
    Get all materials that require baking.
    """
    to_bake = []

    for material in data.materials:
        if requires_bake(material):
            to_bake.append(material)
    
    return to_bake


def main():
    # Ensure Object mode
    if context.mode != 'OBJECT':
        ops.object.editmode_toggle()

    to_bake = get_bake_materials()
    # pprint(to_bake)

    ops.object.select_all(action='SELECT')
    ops.object.convert(target='MESH')

    mesh_objects = [obj for obj in data.objects if obj.type == 'MESH']

    # Add a target UV map for baking
    for mesh_obj in mesh_objects:
        # print(f"Adding target UV map to {mesh_obj.name}")
        mesh_obj.data.uv_layers.new(name="ZenBakeTarget")
        mesh_obj.data.uv_layers.active = mesh_obj.data.uv_layers["ZenBakeTarget"]
        # print(f"Active UV map: {mesh_obj.data.uv_layers.active.name}\n")
    
    ops.object.select_all(action='SELECT')
    ops.object.editmode_toggle()


if __name__ == '__main__':
    # pprint(list(bpy.data.objects))
    # print(sys.argv)
    main()