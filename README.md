# zen3d

zen3d is a command line tool to convert 3D models from a various formats to GLB.

*Note: currently supports Blender files only.* 

## Rationale

The built-in/third-party exporters in all the DCC tools support only a subset of features the artists use and this makes the workflow of creating assets for the web a bit restricting and difficult.

The goal is to build a WYSIWYG conversion tool that can handle popular formats like Blender, 3ds Max, Maya, Cinema 4D, Modo, etc. through a single command line interface, while providing flexibility to artists to continue using their features of choice as much as possible. 

It works by accessing the respective 3D program's Python API, inspects the file data and decides which objects require baking, UV mapping, etc. and eventually outputs a GLB.

## Installation

You can find prebuilt binaries for Windows in the [Releases](https://github.com/salaivv/zen3d/releases) page. Simply download the binary to a folder and call it from the command line using its full path. 

Alternatively, add `zen3d` to the path to use it like any other command like tool.

You will have to update the location of the DCC executables in the `config.json` file (only Blender 3.3 is supported as of now).

Also, ensure that a compatible graphics card is selected in Blender to speed up the baking process.

Building for other platforms should be pretty straightforward. Check the section below on building.

## Usage

To convert a model to GLB, just call the command `zen3d` like this:

```bash
zen3d -i {INPUT_MODEL} -o {OUTPUT_GLB} -r {RESOLUTION}
```

For example,

```bash
zen3d -i chair.blend -o chair.glb -r 2048
```

You can call `zen3d --help` to display the help message with command line options:

```
Usage: zen3d [OPTIONS]

  Zen3D – Convert 3D models to GLTF/GLB

Options:
  -i PATH     Path to the input 3D model  [required]
  -o PATH     Path to the GLTF/GLB output  [required]
  -r INTEGER  Resolution to be used for baking  [default: 2048]
  --help      Show this message and exit
```

The bake resolution defaults to 2048 if not mentioned explicitly. zen3d will bake maps only if it is necessary. There are cases where the entire asset might have only plain materials and no texture maps will be baked in those cases.

## Building

Building binaries uses PyInstaller to package the dependencies. Before you build you need do a few things:

1. Clone this repository.
2. Install the dependencies using `pip install -r requirements.txt`.
3. Create a folder named `tools` in the root of the repo and download `gltfpack` to it.
4. Finally run the following command to build the binary:

```
pyinstaller .\__main__.py -F --add-data '.\converters;.\converters' --add-data '.\tools;.\tools' --name zen3d
```

You will find the binary within the `dist` folder once the build finishes.

## Limitations

General limitations:

- Suitable only for converting single assets and not full-blown scene files.
- Only Blender files are supported for conversion right now.

Blender specific-limitations:

- With respect to shading, Base color, Metallic, Roughness, Emission, Alpha and Normal are supported, but, features like Sheen, Clearcoat, Volumes are not yet supported.
- Transmission takes into account the Transmission value in Principled BSDF, but the output could look different from Blender. Currently it approximates thickness using a constant value.
- GLTF specification features like variants, morph targets, etc. are not supported yet.
- Animations are not supported yet.
- Mix shaders that combine Principled BSDF with other shader nodes are not supported.
- Only a single Principled BSDF node is supported per node tree (ideally it always will be).

## Known issues

- When baking at low resolutions, sometimes island margins extend into other islands causing baking artifacts.
- The produced GLB is not viewable in the windows 3D viewer. Please use the [gltfviewer](https://gltf-viewer.donmccurdy.com/) or the [Babylon viewer](https://sandbox.babylonjs.com/).

If you discover any bugs, please report them to the [Issues](https://github.com/salaivv/zen3d/issues) page and, if possible, attach a link to the model you are trying to convert, so that I can reproduce the bug.

## TODO

- [ ] Start supporting other DCCs like 3ds Max, Maya, etc.
- [ ] Support a wider gamut of features for the existing Blender implementation.
- [ ] Expand the command line options for more flexibility
- [ ] Implement a better system so that supporting a new features (or any custom workflows) becomes plug and play rather than having to change code in a lot of places
- [ ] Implement logging

## Disclaimer

This tool is in very early stage of development and not recommended for any production use. Please use it at your own risk.