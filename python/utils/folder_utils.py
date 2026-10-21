from pathlib import Path
from shutil import copy
import os


def create_model_folder_structure(yaml: dict, model: dict):
    if yaml['ART']['MODULE']['MOHID_WATER']:
        main_path = Path(yaml['MOHID_WATER']['MAIN_PATH'])
    elif yaml['ART']['MODULE']['MOHID_LAND']:
        main_path = Path(yaml['MOHID_LAND']['MAIN_PATH'])
    
    model_path = main_path / model['PATH']
    
    if not os.path.isdir(main_path / "GeneralData/"):
        os.makedirs(main_path / "GeneralData/Bathymetry")
        os.makedirs(main_path / "GeneralData/BoundaryConditions")
        os.makedirs(main_path / "GeneralData/TimeSeries")
    if not os.path.isdir(model_path / "res/"):
        os.makedirs(model_path / "res/Run1/")
    if not os.path.isdir(model_path / "data/"):
        os.makedirs(model_path / "data/")
    if not os.path.isdir(model_path / "exe/"):
        os.makedirs(model_path / "exe/")


def copy_files(files, destination: Path, label, logger):
    """ Copies files into destination, creating it if needed. Nothing is done (no folder created) if files is empty. """
    if len(files) == 0:
        return
    if not os.path.isdir(destination):
        os.makedirs(destination)
    for file in files:
        file_destination = destination / os.path.split(file)[1]
        logger.info(f"{label}: Copying {file} to {file_destination}")
        copy(file, file_destination)
