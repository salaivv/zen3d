import sys
import bpy
from bpy import ops, data, context
from bpy.types import Material
from pprint import pprint


# sys.argv[6] is bake resolution
# sys.argb[7] is output GLB path

def get_material_output(node_tree):
    node_material_output = None

    for node in node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL':
            node_material_output = node
            break
    
    return node_material_output


def requires_bake(material) -> bool:
    """
    Checks if a given material needs to be baked.

    Returns True if needs baking or False if otherwise.
    """
    is_transmission = False
    is_plain = True
    
    node_tree = material.node_tree

    node_material_output = get_material_output(node_tree)

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


def get_mesh_objects():
    for obj in data.objects:
        if obj.type == 'MESH':
            yield obj


def get_bake_materials() -> list[Material]:
    """
    Get all materials that require baking.
    """
    to_bake = []
    materials_used = []

    for material in data.materials:
        if material.users > 0:
            if requires_bake(material):
                to_bake.append(material)
    
    return to_bake


def add_bake_node(node_tree):
    node_material_output = get_material_output(node_tree)

    node_bake_image = node_tree.nodes.new("ShaderNodeTexImage")
    node_bake_image.location[0] = node_material_output.location[0] + 300
    node_bake_image.location[1] = node_material_output.location[1]

    return node_bake_image


def deselect_all_nodes(node_tree):
    for node in node_tree.nodes:
        node.select = False


def main(bake_resolution, glb_output_path):
    # Ensure Object mode
    if context.mode != 'OBJECT':
        ops.object.editmode_toggle()

    materials_to_bake = get_bake_materials()
    # pprint(to_bake)

    ops.object.select_all(action='SELECT')
    ops.object.convert(target='MESH')

    # Add a target UV map for baking
    for mesh_obj in get_mesh_objects():
        # print(f"Adding target UV map to {mesh_obj.name}")
        mesh_obj.data.uv_layers.new(name="ZenBakeTarget")
        mesh_obj.data.uv_layers.active = mesh_obj.data.uv_layers["ZenBakeTarget"]
        # print(f"Active UV map: {mesh_obj.data.uv_layers.active.name}\n")
    
    ops.object.select_all(action='SELECT')  # select all objects
    ops.object.editmode_toggle()  # then switch to edit mode
    ops.mesh.select_all(action='DESELECT') # ensure nothing is selected

    # Select parts of the meshes with materials that
    # require baking for unwrapping
    for mesh_obj in get_mesh_objects():
        context.view_layer.objects.active = mesh_obj

        for slot in context.active_object.material_slots:
            if slot.material and slot.material in materials_to_bake:
                context.active_object.active_material_index = slot.slot_index
                ops.object.material_slot_select()
    
    # Smart UV project 
    ops.uv.smart_project()

    bake_image = data.images.new("bake_image", bake_resolution, bake_resolution)
    for material in materials_to_bake:
        node_bake_image = add_bake_node(material.node_tree)
        node_bake_image.image = bake_image
        deselect_all_nodes(material.node_tree)
        node_bake_image.select = True
        material.node_tree.nodes.active = node_bake_image


if __name__ == '__main__':
    # pprint(list(bpy.data.objects))
    # print(sys.argv)
    main(int(sys.argv[6]), sys.argv[7])