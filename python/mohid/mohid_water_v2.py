import datetime
import glob
import multiprocessing
import os.path
import re
import subprocess
import time
from pathlib import Path
from shutil import copy

import utils.constants as static
import utils.file_modifier as file_modifier
import utils.folder_utils as folder_utils
import utils.mohid_utils as mohid_utils
from common.model_base import ModelBase


MOHID_SUCCESS_MESSAGES = ['Program Mohid Water successfully terminated',
                          'Program Mohid Land successfully terminated']
DDC_SUCCESS_MESSAGES = ["Program MohidDDC successfully terminated"]
DEFAULT_DDC_EXE = "DomainDecompositionConsolidation.exe"


class MohidWater(ModelBase):
    """ MOHID Water model. The simulation dates and the pre-processing / simulation / post-processing cycle are
    handled by ModelBase; this class only runs MOHID Water for the current period: it updates the Model_1.dat
    files, gathers the restart files, runs MOHID (serial, OpenMP or MPI + DDC) and backs up the results.
    """

    def __init__(self, art):
        super().__init__(art, "MOHID Water")
        self.config = self.yaml['MOHID_WATER']

    def run_simulation(self, repeat_index: int):
        main_path = Path(self.config['MAIN_PATH'])
        days_per_run = self.yaml['SIMULATION']['DAYS_PER_RUN']
        models = self.config['MODELS']

        self.check_triggers(repeat_index, days_per_run)

        for model in models.keys():
            folder_utils.create_model_folder_structure(self.yaml, models[model])
            self.change_model_dat(models[model], main_path)
            self.gather_restart_files(models[model], main_path)

        self.write_trigger(self.config['MAIN_PATH'], days_per_run, stage="Running")
        self.run_mohid()

        # Bypass of the consolidation: only the .fin files are consolidated to be able to continue the run
        if not self._run_consolidation_enabled():
            self.backup_decomposedfiles()

        self.backup_simulation()
        self.write_trigger(self.config['MAIN_PATH'], days_per_run, stage="Finished")

    def _mpi_enabled(self):
        return 'MPI' in self.config and self.config['MPI']['ENABLE']

    def _openmp_enabled(self):
        return 'OPENMP' in self.config and self.config['OPENMP']['ENABLE']

    def _run_consolidation_enabled(self):
        """ MohidDDC is run after every MPI run unless RUN_MOHID_CONSOLIDATION is 0. """
        if self._mpi_enabled():
            return self.config['MPI'].get('RUN_MOHID_CONSOLIDATION', 1)
        return True

    def _ddc_exe(self):
        if self._mpi_enabled():
            return self.config['MPI'].get('MOHID_CONSOLIDATION_EXE', DEFAULT_DDC_EXE)
        return DEFAULT_DDC_EXE

    def _date_folder_format(self):
        return self.config.get('filename', "%Y-%m-%d")

    def _verify_log(self, log_file, messages, program):
        # MOHID always writes these strings in the last lines of the logs. We use it to verify that run was successful
        if not mohid_utils.verify_run(log_file, messages):
            self.logger.info(f"{program} NOT SUCCESSFUL")
            raise ValueError(f"{program} NOT SUCCESSFUL")
        self.logger.info(f"{program} successful")

    def run_mohid(self):
        tree_path = self.config['TREE_PATH']
        exe_path = Path(self.config['EXE_PATH'])
        cwd = os.path.dirname(tree_path)
        output_file_name = Path(tree_path + "MOHID_RUN_" + self.current_initial_date.strftime("%Y-%m-%d") + ".log")

        # cwd is the working directory where the command will execute. stdout is the output file of the command
        with open(output_file_name, "w+") as output_file:
            if self._mpi_enabled():
                self.logger.info("Starting MOHID MPI")
                mpi_config = self.config['MPI']
                if 'EXE_PATH' in mpi_config:
                    mpi_exe_path = str(Path(mpi_config['EXE_PATH']))
                else:
                    mpi_exe_path = "mpiexec"
                    self.logger.info("Executable information for MPI missing. Defaulting to mpiexec.")

                processors_flag = "-n" if mpi_exe_path == "srun" else "-np"
                subprocess.run([mpi_exe_path, processors_flag, str(mpi_config['TOTAL_PROCESSORS']), str(exe_path), "&"],
                               cwd=cwd, stdout=output_file)

            elif self._openmp_enabled():
                self.logger.info("Starting MOHID OpenMP")
                openmp_config = self.config['OPENMP']
                if openmp_config.get('EXE_PATH') == "srun":
                    subprocess.run(["srun", "-T", str(openmp_config['TOTAL_PROCESSORS']), str(exe_path), "&"],
                                   cwd=cwd, stdout=output_file)
                else:
                    subprocess.run(str(exe_path), cwd=cwd, stdout=output_file)

            else:
                self.logger.info("Starting MOHID run")
                subprocess.run(str(exe_path), cwd=cwd, stdout=output_file)

        self._verify_log(output_file_name, MOHID_SUCCESS_MESSAGES, "MOHID RUN")

        if self._mpi_enabled() and self._run_consolidation_enabled():
            self.run_ddc()

    def run_ddc(self):
        """ DDC is run when an MPI run is done to join all the results into a single one. """
        self.logger.info("Starting MOHID_DDC")
        tree_path = self.config['TREE_PATH']
        exe_path = Path(self.config['EXE_PATH'])

        ddc_output_folder = Path(tree_path + "/DomainDecomposition_Logs/")
        if not os.path.isdir(ddc_output_folder):
            os.makedirs(ddc_output_folder)

        ddc_output_filename = ddc_output_folder / (
                "DomainDecomposition_" + self.current_initial_date.strftime("%Y-%m-%d") + ".log")
        mohid_ddc_path = Path(tree_path + self._ddc_exe())

        with open(ddc_output_filename, "w+") as mohid_ddc_output_log:
            subprocess.run([str(mohid_ddc_path), str(exe_path), "&"], cwd=os.path.dirname(tree_path),
                           stdout=mohid_ddc_output_log)

        self._verify_log(ddc_output_filename, DDC_SUCCESS_MESSAGES, "MohidDDC")

    @staticmethod
    def _filter_lines(file_path, patterns):
        with open(file_path, "r") as file:
            return "".join(line for line in file.readlines() if any(re.search(p, line) for p in patterns))

    def backup_decomposedfiles(self):
        """ Consolidation bypass: MPI*DecomposedFiles.dat are reduced to their .fin entries so MohidDDC only
        consolidates the restart files (needed to continue the run). Afterwards they are reduced to their .hdf5
        entries. The original file is kept as MPI*DecomposedFiles.datx.
        """
        main_path = Path(self.config['MAIN_PATH'])

        for model in self.config['MODELS'].keys():
            results_path = main_path / Path(self.config['MODELS'][model]["PATH"] + "res/")
            mpi_decomp_files = glob.glob(str(results_path) + r"/MPI*DecomposedFiles.dat")

            if len(mpi_decomp_files) > 0:
                self.logger.info("Backup of MPI*DecomposedFiles.dat")

            for filedec in mpi_decomp_files:
                file_backup = filedec + "x"
                copy(filedec, file_backup)
                with open(filedec, "w") as filedat:
                    filedat.write(self._filter_lines(file_backup, [".fin", ".fin5"]))

            self.run_ddc()

            # The .fin files were already consolidated for the continuation, only the results remain
            for filedec in mpi_decomp_files:
                with open(filedec, "w") as filedat:
                    filedat.write(self._filter_lines(filedec + "x", [".hdf5", ".hdf"]))

    def change_model_dat(self, model, main_path: Path):
        """ MOHID needs the file Model_1.dat to be changed, especially START and END times. This function changes
        that file in each iteration to update START and END and other parameters that can be defined in the yaml.
        """
        self.logger.info(f"Creating new model file for model: {model['NAME']}")
        path = (main_path / model['PATH'] / "data/").expanduser()
        if not os.path.isdir(path):
            self.logger.info("Path for model folder does not exist.")
            self.logger.info("Check path parameters in the yaml file. Exiting ART.")
            raise ValueError("Path for model folder does not exist.")

        file_path = Path(path, "Model_1.dat")
        if not file_path.is_file():
            raise ValueError(f"File {file_path} does not exist.")

        start = file_modifier.date_to_mohid_date(self.current_initial_date)
        end = file_modifier.date_to_mohid_date(self.current_final_date)
        file_modifier.modify_start_dat_date(file_path, start, self.logger)
        self.logger.info(f"Changed START of {file_path} to {start}")
        file_modifier.modify_end_dat_date(file_path, end, self.logger)
        self.logger.info(f"Changed END of {file_path} to {end}")
        file_modifier.modify_line(file_path, "DT", str(model['DT']), self.logger)

        if self._openmp_enabled():
            if 'TOTAL_PROCESSORS' in self.config['OPENMP']:
                num_omp_processors = self.config['OPENMP']['TOTAL_PROCESSORS']
            else:
                self.logger.info("NUM_PROCESSORS not defined. model will use max threads available")
                num_omp_processors = multiprocessing.cpu_count()
            file_modifier.modify_line(file_path, "OPENMP_NUM_THREADS", str(num_omp_processors), self.logger)

        for key, value in model.get('mohidwater.dat', {}).items():
            file_modifier.modify_line(file_path, key, value, self.logger)
        self.logger.info(f"Model {model['NAME']} .dat file was created.")

    def gather_restart_files(self, model: dict, main_path: Path):
        """ Gets restart files from previous run. These files need to be put in /res folder of the project you're
        trying to run.
        """
        self.logger.info(f"Gathering the restart files for model: {model['NAME']}")
        date_format = self._date_folder_format()

        previous_init_date = self.current_initial_date - datetime.timedelta(days=1)
        previous_final_date = previous_init_date + datetime.timedelta(days=self.yaml['SIMULATION']['DAYS_PER_RUN'])
        self.logger.info(f"Restart Files Initial Day: {previous_init_date:{date_format}}")
        self.logger.info(f"Restart Files Final Day: {previous_final_date:{date_format}}")

        path_fin_files = Path(model['STORAGE_PATH']) / ("Restart/" + previous_init_date.strftime(date_format) + "_" +
                                                         previous_final_date.strftime(date_format) + "/")
        self.logger.info(f"Source Restart Files: {path_fin_files}")

        if not os.path.isdir(path_fin_files):
            self.logger.info(f"Restart folder {path_fin_files} does not exist.")
            return

        restart_files_dest = main_path / (model['PATH'] + "res/")
        if not os.path.isdir(restart_files_dest):
            os.makedirs(restart_files_dest)

        # The nomfich.dat file for mohidwater is not changed and when a restart file is generated it ends with _1.fin
        # and because of that an input restart file needs to finish with _0.fin. So we simply change it when we copy it.
        for extension in ("fin", "fin5"):
            for file in glob.glob(str(path_fin_files) + r"/*." + extension):
                file_destination = restart_files_dest / (os.path.split(file)[1].split("_")[0] + "_0." + extension)
                self.logger.info(f"Restart Files: Copying {file} to {file_destination}")
                copy(file, file_destination)

    def _trigger_file_name(self, days_per_run):
        initial_date = self.current_initial_date.strftime("%Y-%m-%d")
        final_date = (self.current_initial_date + datetime.timedelta(days_per_run)).strftime("%Y-%m-%d")
        return initial_date + "_" + final_date + ".dat"

    def check_triggers(self, repeat_index: int, days_per_run: int):
        """ Waits for the trigger files in FOLDERS_TO_WATCH to have status FINISHED. The execution is never
        interrupted by this function, any errors found are reported in the logger.
        """
        if 'TRIGGER' not in self.yaml or not self.yaml['TRIGGER']['ENABLE']:
            return

        trigger_config = self.yaml['TRIGGER']
        if repeat_index != 0 and not trigger_config.get('CHECK_ALL', True):
            return

        folders = trigger_config.get('FOLDERS_TO_WATCH')
        if not folders:
            self.logger.info("No folders to watch on triggers FOLDER_TO_WATCH parameter is empty.")
            return

        if 'TRIGGER_MAX_WAIT_H' in trigger_config:
            timer = trigger_config['TRIGGER_MAX_WAIT_H'] * 3600
        else:
            timer = static.DEFAULT_MAX_WAIT_H * 3600
            self.logger.info("No waiting time on triggers TRIGGER_MAX_WAIT_H parameter is empty. Assigning default "
                             f"max wait time of {static.DEFAULT_MAX_WAIT_H} hours.")

        if 'TRIGGER_POLLING_RATE_S' in trigger_config:
            rate = trigger_config['TRIGGER_POLLING_RATE_S']
        else:
            rate = static.DEFAULT_POLLING_RATE_S
            self.logger.info("No polling rate on triggers. TRIGGER_POLLING_RATE_S is empty. Assigning default "
                             f"polling rate of {static.DEFAULT_POLLING_RATE_S} seconds.")

        for folder in folders:
            file = folder + self._trigger_file_name(days_per_run)
            while not os.path.exists(file):
                self.logger.info("Waiting for Trigger file to be created in watch folder")
                time.sleep(rate)
                timer = timer - rate
                if timer < 0:
                    self.logger.info(f"Reached max waiting time while trying to find file {file}. "
                                     "Resuming execution without the file...")
                    return

            finished = False
            self.logger.info("Checking Trigger file status - will advance when becomes Finished")
            while not finished:
                with open(file, 'r') as f:
                    for line in f.readlines():
                        if line.startswith("STATUS") and "FINISHED" in line:
                            finished = True
                            self.logger.info(f"File {file} found with status FINISHED.")
                if not finished:
                    time.sleep(rate * 2)  # rate is doubled to prevent file error with several opens and closes
                    timer = timer - rate * 2
                    if timer < 0:
                        self.logger.info(f"Reached max waiting time while waiting for file {file} to change "
                                         "status to finished. Resuming execution without the correct status on "
                                         "this file...")
                        return

    def write_trigger(self, main_path, days_per_run, stage):
        """ Writes the trigger file of MOHID Water in <MAIN_PATH>/Logs/Triggers/. The execution is never interrupted
        by this function, any errors found are reported in the logger.
        """
        if 'TRIGGER' not in self.yaml or not self.yaml['TRIGGER']['ENABLE']:
            return

        if not self.yaml['TRIGGER'].get('WRITE_TRIGGER'):
            self.logger.info("Output trigger not set. WRITE_TRIGGER parameter is empty.")
            return

        dest_folder = Path(main_path + r"/Logs/Triggers/")
        if not os.path.isdir(dest_folder):
            os.makedirs(dest_folder)

        filepath = dest_folder / self._trigger_file_name(days_per_run)
        system_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        with open(filepath, 'w') as file:
            file.write('\n')
            file.write('FILE AUTOMATICALLY GENERATED TO BE USED AS TRIGGER')
            file.write('\n')
            file.write('DO NOT EDIT, CHANGE, MOVE, DELETE THIS FILE!')
            file.write('\n')
            file.write('\n')

            if stage == "Running":
                file.write('MOHID is running for the following period:')
            elif stage == "Finished":
                file.write('MOHID forecast and backup finished for the following period:')

            file.write('\n')
            file.write(f'START                         : {file_modifier.date_to_mohid_date(self.current_initial_date)}')
            file.write('\n')
            file.write(f'END                           : {file_modifier.date_to_mohid_date(self.current_final_date)}')
            file.write('\n')

            if stage == "Running":
                file.write('STATUS                        : RUNNING')
            elif stage == "Finished":
                file.write('STATUS                        : FINISHED')

            file.write('\n')
            file.write(f'SYSTEM TIME                   : {system_time}')

    def _copy_files(self, files, destination, label):
        if len(files) == 0:
            return
        if not os.path.isdir(destination):
            os.makedirs(destination)
        for file in files:
            file_destination = destination / os.path.split(file)[1]
            self.logger.info(f"{label}: Copying {file} to {file_destination}")
            copy(file, file_destination)

    @staticmethod
    def _backup_hdf_name(file_name):
        """ Hydrodynamic_1_Surface.hdf5 becomes Hydrodynamic_Surface.hdf5 and Hydrodynamic_1.hdf5 becomes
        Hydrodynamic.hdf5.
        """
        name_array = file_name.split("_")
        if len(name_array) > 2:
            return name_array[0] + "_" + name_array[2]
        return name_array[0] + "." + name_array[-1].split(".")[1]

    def backup_simulation(self):
        """ Backs up all the results located in the res/ folder of every model to its STORAGE_PATH: restart files to
        Restart/, consolidated .hdf5 files to Results_HDF/ (ignoring the non consolidated "MPI_" ones, only the ones
        in RESULTS_LIST when given) and the time series to Results_TimeSeries/. When the consolidation is bypassed the
        MPI decomposed files and the Tree.dat are copied to Results_MPI/ instead of the .hdf5 files.
        """
        date_format = self._date_folder_format()
        initial_date = self.current_initial_date.strftime(date_format)
        final_date = (self.current_initial_date +
                      datetime.timedelta(self.yaml['SIMULATION']['DAYS_PER_RUN'])).strftime(date_format)
        date_path = initial_date + "_" + final_date + "/"

        main_path = Path(self.config['MAIN_PATH'])
        self.logger.info(f"Simulation Results Initial Date: {initial_date}")
        self.logger.info(f"Simulation Results Final Date: {final_date}")

        for model_name, model in self.config['MODELS'].items():
            results_path = main_path / Path(model["PATH"] + "res/")
            generic_path = Path(model['STORAGE_PATH'])

            # ------------  .fin files -------------------------------------------
            if not model.get('HAS_SOLUTION_FROM_FILE'):
                fin_files = glob.glob(str(results_path) + r"/*_1.fin5") + glob.glob(str(results_path) + r"/*_1.fin")
                fin_files = [file for file in fin_files if not os.path.split(file)[1].startswith("MPI")]
                self._copy_files(fin_files, generic_path / "Restart/" / date_path, "Backup Simulation Fin_files")

            if self._run_consolidation_enabled():
                self._backup_hdf_files(model, results_path, generic_path / "Results_HDF/" / date_path)
            else:
                self._backup_mpi_files(results_path, generic_path / "Results_MPI/" / date_path / "res/")

            # ---------------  Time series-------------------------------------
            self._copy_files(glob.glob(str(results_path) + r"/Run1/*.*"),
                             generic_path / "Results_TimeSeries/" / date_path, "Backup Simulation TimeSerie Files")

    def _backup_hdf_files(self, model, results_path, results_storage):
        hdf5_files = [file for file in glob.glob(str(results_path) + r"/*.hdf5")
                      if not os.path.split(file)[1].startswith("MPI")]
        if len(hdf5_files) == 0:
            return
        if not os.path.isdir(results_storage):
            os.makedirs(results_storage)

        for file in hdf5_files:
            file_name = os.path.split(file)[1]
            # if RESULTS_LIST is given, only those result files are backed up. Defaults to all of them
            if 'RESULTS_LIST' in model and file_name not in model['RESULTS_LIST']:
                continue
            file_destination = results_storage / self._backup_hdf_name(file_name)
            self.logger.info(f"Backup Simulation HDF Files: Copying {file} to {file_destination}")
            copy(file, file_destination)

    def _backup_mpi_files(self, results_path, results_mpi_storage):
        mpi_files = glob.glob(str(results_path) + r"/MPI*")
        if len(mpi_files) == 0:
            return
        if not os.path.isdir(results_mpi_storage):
            os.makedirs(results_mpi_storage)

        for file in mpi_files:
            file_destination = results_mpi_storage / os.path.split(file)[1]
            try:
                copy(file, file_destination)
                self.logger.info(f"Backup MPI decomposed Files: Copying {file} to {file_destination}")
            except IOError:
                self.logger.error("Backup MPI decomposed Files NOT SUCCESSFUL")
                raise ValueError("Backup MPI decomposed Files NOT SUCCESSFUL")

        file_destination = results_mpi_storage / "Tree.dat"
        try:
            copy(Path(self.config['TREE_PATH'] + r"/Tree.dat"), file_destination)
            self.logger.info(f"Tree File: Copying to {file_destination}")
        except IOError:
            self.logger.error("Error copying the Tree File")
            raise ValueError("Error copying the Tree File")
