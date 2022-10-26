import os
import json
import typer
import subprocess
from pathlib import Path


APP_NAME = "zen3d"


app = typer.Typer(add_completion=False)


def _get_config(app_dir):
    if not os.path.exists(app_dir):
        os.mkdir(app_dir)

    config_path: Path = Path(typer.get_app_dir(APP_NAME)) / "config.json"
    config = None

    if not config_path.is_file():
        with open(config_path, "w") as f:
            json.dump({}, f)
    else:
        with open(config_path, "r") as f:
            config = json.load(f)

    return config


def _get_converter(app_name):
    this_dir = Path(os.path.abspath(__file__)).parent

    if app_name == "blender":
        converter = this_dir / "converters" / "blender.py"

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

    app_dir = typer.get_app_dir(APP_NAME)

    config = _get_config(app_dir)

    if input_model.suffix == '.blend':
        subprocess.run([config['blender'], str(input_model),
                       '-b', '-P', _get_converter('blender')])

    # print(f"Done converting {input_model.name}.")
    # print(f"Output saved to {output_model}.")


if __name__ == "__main__":
    app()
