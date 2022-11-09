import bpy
import sys
from pprint import pprint
from pathlib import Path
from collections.abc import Iterator
from bpy import ops, data, context
from bpy.types import (Object, Material, Image,
                       ShaderNodeTree, ShaderNode,
                       ShaderNodeTexImage)


def setup_bake_settings(samples: int = 16) -> None:
    context.scene.render.engine = 'CYCLES'
    context.scene.cycles.device = 'GPU'
    context.scene.cycles.samples = samples
    # context.scene.cycles.bake_type = 'EMIT'
    context.scene.cycles.use_denoising = True
    context.scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    context.scene.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    context.scene.cycles.denoising_prefilter = 'ACCURATE'


def get_node_of_type(node_tree: ShaderNodeTree, node_type: str) -> ShaderNode:
    node_of_type = None

    for node in node_tree.nodes:
        if node.type == node_type:
            node_of_type = node
            break

    return node_of_type


def requires_bake(material: Material) -> bool:
    """
    Checks if a given material needs to be baked.

    Returns True if needs baking or False if otherwise.
    """
    is_transmission = False
    is_plain = True

    node_tree = material.node_tree

    node_material_output = get_node_of_type(node_tree, 'OUTPUT_MATERIAL')

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


def get_mesh_objects() -> Iterator[Object]:
    for obj in data.objects:
        if obj.type == 'MESH':
            yield obj


def get_bake_materials() -> Iterator[Material]:
    """
    Get all materials that require baking.
    """
    for material in data.materials:
        if material.users > 0:
            if requires_bake(material):
                yield material


def deselect_nodes_all(node_tree: ShaderNodeTree) -> None:
    for node in node_tree.nodes:
        node.select = False


def set_only_active_node(node_tree: ShaderNodeTree, node: ShaderNode) -> None:
    deselect_nodes_all(node_tree)
    node.select = True
    node_tree.nodes.active = node


def add_bake_node(node_tree: ShaderNodeTree) -> ShaderNodeTexImage:
    node_material_output = get_node_of_type(node_tree, 'OUTPUT_MATERIAL')

    node_bake = node_tree.nodes.new("ShaderNodeTexImage")
    node_bake.location[0] = node_material_output.location[0] + 300
    node_bake.location[1] = node_material_output.location[1]

    return node_bake


def bake_principled_socket(
    materials: Iterator[Material],
    bake_image: Image, socket_name: str,
    bake_dir: str, suffix: str
) -> None:
    # TODO Determine if a socket needs baking.
    # If none of the materials have anything connected to a socket
    # then there's no need to bake that socket

    node_data = {}

    for material in materials:
        node_tree = material.node_tree
        node_bake = add_bake_node(node_tree)
        node_bake.image = bake_image
        node_principled = get_node_of_type(node_tree, 'BSDF_PRINCIPLED')
        node_material_output = get_node_of_type(node_tree, 'OUTPUT_MATERIAL')

        # Add an Emission node
        node_emission = node_tree.nodes.new('ShaderNodeEmission')

        node_data[node_tree] = {
            'node_bake': node_bake,
            'node_principled': node_principled,
            'node_material_output': node_material_output,
            'node_emission': node_emission
        }

        # Find the socket connected to the given socket
        socket = node_principled.inputs[socket_name]
        from_socket = None

        if socket.links:
            from_socket = socket.links[0].from_socket
        else:
            node_color = None

            if type(socket.default_value) == float:
                node_color = node_tree.nodes.new('ShaderNodeValue')
            else:
                node_color = node_tree.nodes.new('ShaderNodeRGB')

            node_color.outputs[0].default_value = socket.default_value
            from_socket = node_color.outputs[0]
            node_data[node_tree]['other'] = node_color

        to_socket = node_emission.inputs['Color']

        # Connect the found socket to the Emission Color input
        node_tree.links.new(from_socket, to_socket)

        # Connect the Emission BSDF output to the Surface input of Material Output
        node_tree.links.new(node_emission.outputs[0], node_material_output.inputs['Surface'])

        # Set the bake node as active and the only selected node
        set_only_active_node(node_tree, node_bake)

    # Set the bake type to Emit
    context.scene.cycles.bake_type = 'EMIT'

    # Bake map
    ops.object.bake(type='EMIT')

    # Save the image to the disk
    bake_image.save_render(filepath=str(Path(bake_dir) / f"test_1_{suffix}.png"))

    # Restore node tree to its original state
    for node_tree, node_tree_data in node_data.items():
        # Delete the emission node
        node_tree.nodes.remove(node_tree_data['node_emission'])
        node_tree.nodes.remove(node_tree_data['node_bake'])

        if 'other' in node_tree_data.keys():
            node_tree.nodes.remove(node_tree_data['other'])

        # Connect Principled back to the material output node
        node_tree.links.new(node_tree_data['node_principled'].outputs[0],
                            node_tree_data['node_material_output'].inputs['Surface'])


def main(bake_resolution: int, glb_output_path: str) -> None:
    # Ensure Object mode
    if context.mode != 'OBJECT':
        ops.object.mode_set(mode='OBJECT')

    # pprint(to_bake)

    ops.object.select_all(action='SELECT')
    ops.object.convert(target='MESH')
    ops.object.select_all(action='DESELECT')

    # Add a target UV map for baking
    for mesh_obj in get_mesh_objects():
        # print(f"Adding target UV map to {mesh_obj.name}")
        mesh_obj.data.uv_layers.new(name="ZenBakeTarget")
        mesh_obj.data.uv_layers.active = mesh_obj.data.uv_layers["ZenBakeTarget"]
        # print(f"Active UV map: {mesh_obj.data.uv_layers.active.name}\n")
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj

    ops.object.editmode_toggle()  # then switch to edit mode
    ops.mesh.select_all(action='DESELECT')  # ensure nothing is selected

    # Select parts of the meshes with materials that
    # require baking for unwrapping
    for mesh_obj in get_mesh_objects():
        context.view_layer.objects.active = mesh_obj

        for slot in context.active_object.material_slots:
            if slot.material and slot.material in get_bake_materials():
                context.active_object.active_material_index = slot.slot_index
                ops.object.material_slot_select()

    # Smart UV project
    ops.uv.smart_project()

    # Create a new image and setup bake node for materials
    bake_image = data.images.new("bake_image", bake_resolution, bake_resolution)

    setup_bake_settings()

    bake_dir = str(Path(glb_output_path).parent)

    bake_principled_socket(get_bake_materials(), bake_image, 'Base Color', bake_dir, 'ALBEDO')
    bake_principled_socket(get_bake_materials(), bake_image, 'Metallic', bake_dir, 'METAL')
    bake_principled_socket(get_bake_materials(), bake_image, 'Roughness', bake_dir, 'ROUGH')

    ops.wm.save_mainfile(filepath=str(Path(bake_dir) / "test_1.blend"))


if __name__ == '__main__':
    # sys.argv[6] is bake resolution
    # sys.argb[7] is output GLB path
    main(int(sys.argv[6]), sys.argv[7])
