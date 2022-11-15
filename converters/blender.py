import os
import bpy
import sys
import json
import subprocess
from pprint import pprint
from pathlib import Path
from typing import Union, List
from tempfile import TemporaryDirectory
from collections.abc import Iterator
from bpy import ops, data, context
from bpy.types import (Object, Material, Image,
                       ShaderNodeTree, ShaderNode,
                       ShaderNodeTexImage)


def setup_bake_settings(samples: int = 16) -> None:
    context.scene.render.engine = 'CYCLES'
    context.scene.cycles.device = 'GPU'
    context.scene.cycles.samples = samples
    context.scene.cycles.use_denoising = True
    context.scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    context.scene.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    context.scene.cycles.denoising_prefilter = 'ACCURATE'
    context.scene.view_settings.view_transform = 'Standard'
    context.scene.render.bake.margin_type = 'EXTEND'
    context.scene.render.bake.margin = 4


def get_node_of_type(node_tree: ShaderNodeTree, node_type: str) -> ShaderNode:
    node_of_type = None

    for node in node_tree.nodes:
        if node.type == node_type:
            node_of_type = node
            break

    return node_of_type


def requires_bake(material: Material) -> tuple[bool, bool]:
    """
    Checks if a given material needs to be baked.

    Returns True if needs baking or False if otherwise.
    """
    is_transmission = False
    is_plain = True

    node_tree = material.node_tree
    if node_tree:
        node_material_output = get_node_of_type(node_tree, 'OUTPUT_MATERIAL')

        node_principled = node_material_output.inputs["Surface"].links[0].from_node

        for i in node_principled.inputs:
            if len(i.links) > 0:
                is_plain = False
                break

        if node_principled.inputs["Transmission"].default_value > 0:
            is_transmission = True

        if is_plain and is_transmission:
            return False, True
        elif not is_plain and is_transmission:
            return True, True
        elif is_plain and not is_transmission:
            return False, False
        else:
            return True, False
    else:
        return False, False


def get_mesh_objects() -> List[Object]:
    mesh_objects = []
    for obj in data.objects:
        if obj.type == 'MESH':
            mesh_objects.append(obj)
    return mesh_objects


def get_bake_materials() -> tuple[List[Material], List[Material]]:
    """
    Get all materials that require baking.
    """
    to_bake = []
    transmission = []
    for material in data.materials:
        if material.users > 0:
            if requires_bake(material)[1]:
                transmission.append(material)
            if requires_bake(material)[0]:
                to_bake.append(material)
    return to_bake, transmission


def get_thickness(material: Material) -> float:
    for mesh_object in get_mesh_objects():
        if material.name in mesh_object.data.materials:
            return round(min(list(mesh_object.dimensions)), 2)


def deselect_nodes_all(node_tree: ShaderNodeTree) -> None:
    for node in node_tree.nodes:
        node.select = False


def set_only_active_node(node_tree: ShaderNodeTree, node: ShaderNode) -> None:
    deselect_nodes_all(node_tree)
    node.select = True
    node_tree.nodes.active = node


def add_bake_node(node_tree: ShaderNodeTree, bake_image: Image) -> ShaderNodeTexImage:
    node_material_output = get_node_of_type(node_tree, 'OUTPUT_MATERIAL')

    node_bake = node_tree.nodes.new("ShaderNodeTexImage")
    node_bake.image = bake_image
    node_bake.location[0] = node_material_output.location[0] + 300
    node_bake.location[1] = node_material_output.location[1]

    return node_bake


def bake_principled_socket(
    materials: List[Material],
    bake_image: Image, bake_dir: str,
    socket_name: str, suffix: str
) -> Union[Image, None]:

    socket_requires_bake = False
    for material in materials:
        node_principled = get_node_of_type(material.node_tree, 'BSDF_PRINCIPLED')
        if node_principled.inputs[socket_name].links:
            socket_requires_bake = True
            break
    
    if socket_requires_bake:
        node_data = {}

        for material in materials:
            node_tree = material.node_tree
            node_bake = add_bake_node(node_tree, bake_image)
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

        # Bake map
        ops.object.bake(type='EMIT')

        # Save the image to the disk
        bake_image_path = str(Path(bake_dir) / f"{Path(data.filepath).stem}_{suffix}.png")
        bake_image.save_render(filepath=bake_image_path)

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
        
        return data.images.load(bake_image_path)
    
    else:
        return None


def bake_map(
    materials: List[Material],
    bake_image: Image, bake_dir: str,
    bake_type: str, suffix: str
) -> Image:
    
    nodes_bake = {}

    for material in materials:
        node_tree = material.node_tree
        node_bake = add_bake_node(node_tree, bake_image)

        nodes_bake[node_tree] = node_bake

        set_only_active_node(node_tree, node_bake)

    ops.object.bake(type=bake_type)

    bake_image_path = str(Path(bake_dir) / f"{Path(data.filepath).stem}_{suffix}.png")
    bake_image.save_render(filepath=bake_image_path)

    for node_tree, node_bake in nodes_bake.items():
        node_tree.nodes.remove(node_bake)
    
    return data.images.load(bake_image_path)


def main(bake_resolution: int, glb_output_path: str, gltfpack: str) -> None:
    bake_dir = TemporaryDirectory()

    # Ensure Object mode
    if context.mode != 'OBJECT':
        ops.object.mode_set(mode='OBJECT')
    
    mesh_objects = get_mesh_objects()

    # pprint(to_bake)
    for mesh_obj in mesh_objects:
        context.view_layer.objects.active = mesh_obj
        break

    ops.object.select_all(action='SELECT')
    ops.object.convert(target='MESH')
    ops.object.select_all(action='DESELECT')

    mesh_objects = get_mesh_objects()

    # Add a target UV map for baking
    for mesh_obj in mesh_objects:
        # print(f"Adding target UV map to {mesh_obj.name}")
        mesh_obj.data.uv_layers.new(name="ZenBakeTarget")
        mesh_obj.data.uv_layers.active = mesh_obj.data.uv_layers["ZenBakeTarget"]
        # print(f"Active UV map: {mesh_obj.data.uv_layers.active.name}\n")
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj

        if len(mesh_obj.data.materials) == 0:
            if len(mesh_obj.material_slots) == 0:
                ops.object.material_slot_add()
            material = data.materials.new('Material')
            material.use_nodes = True
            mesh_obj.material_slots[0].material = material

    ops.object.editmode_toggle()  # then switch to edit mode
    ops.mesh.select_all(action='DESELECT')  # ensure nothing is selected

    bake_materials, trans_materials = get_bake_materials()[0], get_bake_materials()[1]

    # Select parts of the meshes with materials that
    # require baking for unwrapping
    for mesh_obj in mesh_objects:
        context.view_layer.objects.active = mesh_obj

        for slot in context.active_object.material_slots:
            if slot.material:
                if slot.material in bake_materials:
                    context.active_object.active_material_index = slot.slot_index
                    ops.object.material_slot_select()

    # Smart UV project
    ops.uv.smart_project(angle_limit=1.151917, island_margin=0.005, area_weight=0.75)

    # Create a new image and setup bake node for materials
    bake_image = data.images.new("bake_image", bake_resolution, bake_resolution)

    setup_bake_settings()

    baked_maps = { }

    baked_maps["Base Color"] = bake_principled_socket(bake_materials, bake_image,
                                                      bake_dir.name, "Base Color", 'ALBEDO')
    baked_maps["Metallic"] = bake_principled_socket(bake_materials, bake_image,
                                                    bake_dir.name, "Metallic", 'METAL')
    baked_maps["Roughness"] = bake_principled_socket(bake_materials, bake_image,
                                                     bake_dir.name, "Roughness", 'ROUGH')
    baked_maps["Emission"] = bake_principled_socket(bake_materials, bake_image,
                                                    bake_dir.name, "Emission", 'EMIT')
    baked_maps["Alpha"] = bake_principled_socket(bake_materials, bake_image,
                                                 bake_dir.name, "Alpha", 'OPACITY')
    baked_maps["Normal"] = bake_map(bake_materials, bake_image,
                                    bake_dir.name, 'NORMAL', 'NORMAL')

    for material in bake_materials:
        # Remove all nodes except Principled and Material Output
        node_tree = material.node_tree
        node_principled = get_node_of_type(node_tree, 'BSDF_PRINCIPLED')

        if node_principled.inputs['Alpha'].links:
            material.blend_method = 'CLIP'
        elif node_principled.inputs['Alpha'].default_value < 1:
            material.blend_method = 'CLIP'

        for node in node_tree.nodes:
            if node.type not in ['BSDF_PRINCIPLED', 'OUTPUT_MATERIAL']:
                node_tree.nodes.remove(node)

        # Setup all baked maps 
        for baked_map_name, baked_map in baked_maps.items():
            if baked_map:
                node_image_tex = node_tree.nodes.new("ShaderNodeTexImage")
                node_image_tex.image = baked_map
                
                if not baked_map_name in ['Base Color']:
                    baked_map.colorspace_settings.name = 'Non-Color'
                
                if baked_map_name == 'Normal':
                    node_normal_map = node_tree.nodes.new('ShaderNodeNormalMap')
                    from_socket = node_image_tex.outputs[0]
                    to_socket = node_normal_map.inputs['Color']
                    node_tree.links.new(from_socket, to_socket)

                    from_socket = node_normal_map.outputs[0]
                    to_socket = node_principled.inputs[baked_map_name]
                    node_tree.links.new(from_socket, to_socket)

                    continue
                
                from_socket = node_image_tex.outputs[0]
                to_socket = node_principled.inputs[baked_map_name]
                node_tree.links.new(from_socket, to_socket)
    
    for mesh_obj in mesh_objects:
        uv_layers = mesh_obj.data.uv_layers
        context.view_layer.objects.active = mesh_obj

        while True:
            for uv_layer in uv_layers:
                if uv_layer.name != 'ZenBakeTarget':
                    uv_layer.active = True
                    ops.mesh.uv_texture_remove()
                    # uv_layers.remove(uv_layer)
            
            if not len(uv_layers) > 1:
                break

    gltf_output_name = os.path.splitext(Path(glb_output_path).name)[0] + '.gltf'
    gltf_output_path = str(Path(bake_dir.name) / gltf_output_name)
    ops.export_scene.gltf(filepath=gltf_output_path, export_format='GLTF_SEPARATE')

    with open(gltf_output_path, 'r') as f:
        gltf = json.load(f)

    if 'extensionsUsed' in gltf.keys():
        gltf['extensionsUsed'].append('KHR_materials_volume')
    else:
        gltf['extensionsUsed'] = []
        gltf['extensionsUsed'].append('KHR_materials_volume')

    for material in trans_materials:
        node_principled = get_node_of_type(material.node_tree, 'BSDF_PRINCIPLED')
        for gltf_mat in gltf['materials']:
            if material.name == gltf_mat['name']:
                gltf_mat['extensions'] = {
                    "KHR_materials_transmission": {
                        "transmissionFactor": node_principled.inputs['Transmission'].default_value
                    },
                    "KHR_materials_volume": {
                        "thicknessFactor": get_thickness(material)
                    }
                }

                break
    
    with open(gltf_output_path, 'w') as f:
        json.dump(gltf, f)

    subprocess.run([gltfpack, '-i', gltf_output_path, '-o', glb_output_path])

    # ops.wm.save_mainfile(filepath=str(
    #     Path(glb_output_path).parent / f"{Path(glb_output_path).name}_baked.blend"))


if __name__ == "__main__":
    # sys.argv[6] is bake resolution
    # sys.argb[7] is output GLB path
    # sys.argb[8] is path to gltfpack
    main(int(sys.argv[6]), sys.argv[7], sys.argv[8])
