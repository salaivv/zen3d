import os
import sys
import json
import time
import typer
import subprocess
from pathlib import Path


APP_NAME = "zen3d"
ZEN_PATH = Path(os.path.abspath(__file__)).parent
GLTF_PACK = ZEN_PATH / 'tools' / 'gltfpack.exe'

app = typer.Typer(add_completion=False)


def _get_config():
    # if not os.path.exists(app_dir):
    #     os.mkdir(app_dir)

    # config_path: Path = Path(typer.get_app_dir(APP_NAME)) / "config.json"
    # config = None

    # if not config_path.is_file():
    #     with open(config_path, "w") as f:
    #         json.dump({}, f)
    # else:
    #     with open(config_path, "r") as f:
    #         config = json.load(f)

    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        config_path = Path(sys.executable).parent / 'config.json'
    else:
        config_path = Path(ZEN_PATH) / "config.json"

    with open(config_path, 'r') as f:
        return json.load(f)


def _get_converter(app_name):
    if app_name == "blender":
        converter = ZEN_PATH / "converters" / "blender.py"

    return str(converter)


@app.command()
def convert(
    input_model: Path = typer.Option(
        ...,
        "-i",
        help="Path to the input 3D model",
        resolve_path=True,
        exists=True
    ),
    output_model: Path = typer.Option(
        ...,
        "-o",
        help="Path to the GLTF/GLB output",
        resolve_path=True
    ),
    resolution: int = typer.Option(
        2048,
        "-r",
        help="Resolution to be used for baking")
):
    """
    Zen3D – Convert 3D models to GLTF/GLB
    """

    # app_dir = typer.get_app_dir(APP_NAME)

    # config = _get_config(app_dir)
    config = _get_config()

    if input_model.suffix == '.blend':
        start = time.time()

        subprocess.run([config['blender'], str(input_model), '-b', '-P',
                       _get_converter('blender'), '--', str(resolution), output_model, GLTF_PACK])

        end = time.time()

        print(f"\nDone conversion in {round(end - start)} seconds.\n")

    # print(f"Done converting {input_model.name}.")
    # print(f"Output saved to {output_model}.")


if __name__ == "__main__":
    app()
