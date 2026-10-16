from pathlib import Path
from shutil import copy
from common import logger
# import mohid.util.constants as static
import utils.constants as static
# import mohid.util.file_modifier as file_modifier
import utils.file_modifier as file_modifier
import datetime
import glob
import os.path
import common.pre_processing as pre_processing
import common.post_processing as post_processing
# import mohid.util.folder_utils as folder_utils
import utils.folder_utils as folder_utils
# import mohid.util.mohid_utils as mohid_utils
import utils.mohid_utils as mohid_utils
from common.model_base import ModelBase
import subprocess
import time
import multiprocessing
#import threading
import re


# class MohidWater:
class MohidWater(ModelBase):  # keeps its own execute/set_global_dates for now; ModelBase provides the common cycle
    def __init__(self, art):
        self.logger = art.logger
        self.yaml = art.yaml
        self.global_initial_date = None
        self.global_final_date = None
        self.number_of_runs = None
        self.current_initial_date = None
        self.current_final_date = None

    def execute(self):
        self.set_global_dates()
        artconfig_keys = self.yaml['ART'].keys()
        simulation_keys = self.yaml['SIMULATION'].keys()
        repeat_index = 0
        if 'OPERATIONAL_MODE' in self.yaml['SIMULATION'].keys() and self.yaml['SIMULATION']['OPERATIONAL_MODE']:
            self.logger.info("Running Mohid Water in Operational Mode")

            if 'AUTOMATIC_DATE' in simulation_keys and self.yaml['SIMULATION']['AUTOMATIC_DATE']:
                today = datetime.datetime.today()
            else:
                print('new',self.yaml['SIMULATION'])

                # No caso de se querer simular o esquema operational em modo hindcast
                # Ler aqui o ficheiro de control_art.dat (tem de estar no mesmo local que o art.yaml)
                with open("control.dat", "r") as file:
                    file_lines = file.readlines()
                    number_of_lines = len(file_lines)
                    for n in range(0,number_of_lines):
                        line = file_lines[n]        
                        if re.search("^START.+:", line):
                            StartDate = line.split()    
                today = datetime.datetime(int(StartDate[2]),int(StartDate[3]),int(StartDate[4]),int(StartDate[5]),0,0)
                #today = datetime.datetime.strptime(self.yaml['SIMULATION']['START_DATE'],static.DATE_FORMAT)
            
            # Time needs to start on hour 00:00:00 otherwise will start the models at the wrong time
            today = today.replace(minute=00, hour=00, second=00)
            self.global_initial_date = today + datetime.timedelta(days=self.yaml['SIMULATION']['REF_DAYS_TO_START'])

            for i in range(1, self.number_of_runs + 1):
                self.current_initial_date = self.global_initial_date + datetime.timedelta(days=i - 1)
                self.current_final_date = self.current_initial_date + datetime.timedelta(
                    days=self.yaml['SIMULATION']['DAYS_PER_RUN'])

                self.logger.info("========================================")
                self.logger.info("STARTING FORECAST ( " + str(i) + " of " + str(self.number_of_runs) + " )")
                self.logger.info("========================================")

                if 'PRE_PROCESSING' in artconfig_keys and self.yaml['ART']['PRE_PROCESSING']:
                    self.logger.info("Executing Pre Processing")
                    pre_processing.execute(self.yaml, self.logger, self.current_initial_date, self.current_final_date,repeat_index)
                if 'RUN_SIMULATION' in artconfig_keys and self.yaml['ART']['RUN_SIMULATION']:
                    self.run_simulation(repeat_index)
                if 'POST_PROCESSING' in artconfig_keys and self.yaml['ART']['POST_PROCESSING']:
                    self.logger.info("Executing Post Processing")
                    post_processing.execute(self.yaml, self.logger, self.current_initial_date, self.current_final_date,repeat_index)
                    # thread = threading.Thread(target=post_processing.execute, args=(self,))
                    # thread = threading.Thread(target=post_processing.execute, args=(self.yaml, self.logger, self.current_initial_date, self.current_final_date))
                    # thread.start()
        else:

            if 'MONTH_MODE' in simulation_keys and self.yaml['SIMULATION']['MONTH_MODE']:
                self.logger.info("Month mode activated. Time skips will be of 1 month each.")
                self.current_initial_date = self.global_initial_date.replace(minute=00, hour=00, second=00)

                if self.current_initial_date.month == 12:
                    self.current_final_date = self.global_initial_date.replace(day=1, month=1,
                                                                               year=self.global_initial_date.year + 1,
                                                                               minute=00, hour=00, second=00)
                else:
                    self.current_final_date = self.global_initial_date.replace(day=1,
                                                                               month=self.global_initial_date.month + 1,
                                                                               minute=00, hour=00, second=00)
            else:
                self.current_initial_date = self.global_initial_date.replace(minute=00, hour=00, second=00)
                self.current_final_date = self.global_initial_date + datetime.timedelta(
                    days=self.yaml['SIMULATION']['DAYS_PER_RUN'])
            if(self.current_final_date <= self.global_final_date.replace(minute=00, hour=00, second=00)):

                while self.current_final_date <= self.global_final_date.replace(minute=00, hour=00, second=00):
                    self.logger.info("========================================")
                    self.logger.info("STARTING FORECAST (" + self.current_initial_date.strftime("%Y-%m-%d") + " to " +
                                    self.current_final_date.strftime("%Y-%m-%d") + ")")
                    self.logger.info("========================================")
                    if 'PRE_PROCESSING' in artconfig_keys and self.yaml['ART']['PRE_PROCESSING']:
                        self.logger.info("Executing Pre Processing")
                        pre_processing.execute(self.yaml, self.logger, self.current_initial_date, self.current_final_date,repeat_index)
                    if self.yaml['ART']['RUN_SIMULATION']:
                        self.run_simulation(repeat_index)
                    if 'POST_PROCESSING' in artconfig_keys and self.yaml['ART']['POST_PROCESSING']:
                        post_processing.execute(self.yaml, self.logger, self.current_initial_date, self.current_final_date,repeat_index)
                        self.logger.info("Executing Post Processing")
                    if 'RUN_TWICE' in self.yaml['ART'].keys() and self.yaml['ART']['RUN_TWICE']:
                        # Only run next day after repeating current day. Useful for up-scaling
                        repeat_index += 1
                        if repeat_index == 1:
                            self.current_initial_date = self.current_initial_date + datetime.timedelta(
                                days=self.yaml['SIMULATION']['DAYS_PER_RUN'])
                            self.current_final_date = self.current_final_date + datetime.timedelta(
                                days=self.yaml['SIMULATION']['DAYS_PER_RUN'])
                        elif repeat_index == 2:
                            repeat_index = 0
                    if self.yaml['SIMULATION']['MONTH_MODE']:
                        self.current_initial_date = self.current_final_date
                        if self.current_initial_date.month == 12:
                            self.current_final_date = self.current_initial_date.replace(day=1, month=1,
                                                                                        year=self.current_initial_date.year + 1,
                                                                                        minute=00, hour=00, second=00)
                        else:
                            self.current_final_date = self.current_initial_date.replace(day=1,
                                                                                        month=self.current_initial_date.month + 1,
                                                                                        minute=00, hour=00, second=00)
                    else:
                        self.current_initial_date = self.current_initial_date + datetime.timedelta(
                            days=self.yaml['SIMULATION']['DAYS_PER_RUN'])
                        self.current_final_date = self.current_final_date + datetime.timedelta(
                            days=self.yaml['SIMULATION']['DAYS_PER_RUN'])
            else:
                self.logger.error("Time Date range is not big enough for a month run.")
            return None

    '''
    Main cycle for the ART run. It has all the functions that are needed for a project.
    '''

    def run_simulation(self, repeat_index: int) :
        main_path = Path(self.yaml['MOHID_WATER']['MAIN_PATH'])
        days_per_run = self.yaml['SIMULATION']['DAYS_PER_RUN']
        self.check_triggers(repeat_index, self.yaml['SIMULATION']['DAYS_PER_RUN'])
        mohid_water_config = self.yaml['MOHID_WATER']
        mohid_water_models = mohid_water_config['MODELS']
        run_mohidddc = 1


        # Aqui testar se é para o bypass
    
        if 'MPI' in self.yaml['MOHID_WATER'].keys() and self.yaml['MOHID_WATER']['MPI']['ENABLE']:
            if 'RUN_MOHID_CONSOLIDATION' in self.yaml['MOHID_WATER']['MPI']:
                run_mohidddc = self.yaml['MOHID_WATER']['MPI']['RUN_MOHID_CONSOLIDATION']
        
        for model in mohid_water_models.keys():
            folder_utils.create_model_folder_structure(self.yaml, mohid_water_models[model])
            self.change_model_dat(mohid_water_models[model], main_path)
            self.gather_restart_files(mohid_water_models[model], main_path)

        self.write_trigger(self.yaml['MOHID_WATER']['MAIN_PATH'],
                          days_per_run, stage="Running")
        self.run_mohid()
                        
        if run_mohidddc == 0:
            self.backup_decomposedfiles()
            
        self.backup_simulation()
        self.write_trigger(self.yaml['MOHID_WATER']['MAIN_PATH'],
                           days_per_run, stage="Finished")

    def set_global_dates(self):
        if 'SIMULATION' not in self.yaml:
            raise ValueError("SIMULATION key not defined in yaml configuration file.")
        simulation_keys = self.yaml['SIMULATION'].keys()
        if 'OPERATIONAL_MODE' in simulation_keys and self.yaml['SIMULATION']['OPERATIONAL_MODE']:
            self.logger.info("Running in Operational Mode")

            if 'AUTOMATIC_DATE' in simulation_keys and self.yaml['SIMULATION']['AUTOMATIC_DATE']:
                today = datetime.datetime.today()
            else:
                print('new',self.yaml['SIMULATION'])
                # No caso de se querer simular o esquema operational em modo hindcast
                # Ler aqui o ficheiro de control_art.dat (tem de estar no mesmo local que o art.yaml)
                with open("control.dat", "r") as file:
                    file_lines = file.readlines()
                    number_of_lines = len(file_lines)
                    for n in range(0,number_of_lines):
                        line = file_lines[n]        
                        if re.search("^START.+:", line):
                            StartDate = line.split()    
                today = datetime.datetime(int(StartDate[2]),int(StartDate[3]),int(StartDate[4]),int(StartDate[5]),0,0)
                #today = datetime.datetime.strptime(self.yaml['SIMULATION']['START_DATE'], static.DATE_FORMAT)
            
            today = today.replace(minute=00, hour=00, second=00)    
            self.global_initial_date = today + datetime.timedelta(days=self.yaml['SIMULATION']['REF_DAYS_TO_START'])
            self.global_final_date = (today + datetime.timedelta(days=self.yaml['SIMULATION']['NUMBER_OF_RUNS'])
                                      + datetime.timedelta(days=self.yaml['SIMULATION']['DAYS_PER_RUN'] - 1))
            self.number_of_runs = self.yaml['SIMULATION']['NUMBER_OF_RUNS']
            initial_date = self.global_initial_date
            final_date = initial_date + datetime.timedelta(days=self.yaml['SIMULATION']['DAYS_PER_RUN'])
            self.logger.info("Initial Date : " + initial_date.strftime(static.DATE_FORMAT))
            # self.logger.info("Final Date: " + final_date.strftime(static.DATE_FORMAT))
            self.logger.info("Final Date: " + self.global_final_date.strftime(static.DATE_FORMAT))
            self.logger.info("Number of runs : " + str(self.number_of_runs))
        elif 'OPERATIONAL_MODE' in simulation_keys:
            try:
                self.logger.info("Running in Normal Mode")
                self.global_initial_date = datetime.datetime.strptime(self.yaml['SIMULATION']['START_DATE'],
                                                                      static.DATE_FORMAT)
                self.global_final_date = datetime.datetime.strptime(self.yaml['SIMULATION']['END_DATE'],
                                                                    static.DATE_FORMAT)

                difference = self.global_final_date - self.global_initial_date
                self.number_of_runs = difference.days
            except KeyError:
                self.logger.warning("KeyError")
                self.number_of_runs = 1
                global_initial_date = datetime.datetime.today()
                global_final_date = global_initial_date + datetime.timedelta(
                    days=self.yaml['SIMULATION']['DAYS_PER_RUN'])
                self.global_initial_date = datetime.datetime.strftime(datetime.datetime.today(), static.DATE_FORMAT)
                self.global_final_date = datetime.datetime.strftime(global_final_date, static.DATE_FORMAT)
            finally:
                self.logger.info("Global Initial Date : " + self.global_initial_date.strftime(static.DATE_FORMAT))
                self.logger.info("Global Final Date : " + self.global_final_date.strftime(static.DATE_FORMAT))
                self.logger.info("Number of runs : " + str(self.number_of_runs))
        else:
            raise ValueError("OPERATIONAL_MODE keyword must be defined in yaml file.")

    def run_mohid(self):
        output_file_name = Path(self.yaml['MOHID_WATER']['TREE_PATH'] + "MOHID_RUN_" + self.current_initial_date.strftime("%Y-%m-%d") + ".log")
        output_file = open(output_file_name, "w+")
        exe_path = Path(self.yaml['MOHID_WATER']['EXE_PATH'])
        tree_path = Path(self.yaml['MOHID_WATER']['TREE_PATH'])
        run_mohidddc = 1
        mohid_ddc_exe = "DomainDecompositionConsolidation.exe"
        srun = 0

        if 'MPI' in self.yaml['MOHID_WATER'].keys() and self.yaml['MOHID_WATER']['MPI']['ENABLE']:
            self.logger.info("Starting MOHID MPI")
            # cwd is the working directory where the command will execute. stdout is the output file of the command
            if 'EXE_PATH' in self.yaml['MOHID_WATER']['MPI']:
                mpi_exe_path = Path(self.yaml['MOHID_WATER']['MPI']['EXE_PATH'])
            else:
                mpi_exe_path = "mpiexec"
                self.logger.info(
                    "Executable information for MPI missing. Defaulting to main EXE: " + exe_path.__str__())

            if 'RUN_MOHID_CONSOLIDATION' in self.yaml['MOHID_WATER']['MPI']:
                run_mohidddc = self.yaml['MOHID_WATER']['MPI']['RUN_MOHID_CONSOLIDATION']

            if 'MOHID_CONSOLIDATION_EXE' in self.yaml['MOHID_WATER']['MPI']:
                mohid_ddc_exe = self.yaml['MOHID_WATER']['MPI']['MOHID_CONSOLIDATION_EXE']
    
            if mpi_exe_path.__str__() == "srun":

                subprocess.run([mpi_exe_path.__str__(), "-n", str(self.yaml['MOHID_WATER']['MPI']['TOTAL_PROCESSORS']),
                #subprocess.run([mpi_exe_path.__str__(), "-n $SLURM_NTASKS",
                                str(exe_path), "&"], cwd=os.path.dirname(self.yaml['MOHID_WATER']['TREE_PATH']),
                              stdout=output_file)
                output_file.close()
            
            else:
                subprocess.run([mpi_exe_path.__str__(), "-np", str(self.yaml['MOHID_WATER']['MPI']['TOTAL_PROCESSORS']),
                                str(exe_path), "&"], cwd=os.path.dirname(self.yaml['MOHID_WATER']['TREE_PATH']),
                              stdout=output_file)
                output_file.close()
                
 
            # Mohid always writes these strings in the last lines of the logs. We use it to verify that run was
            # successful
            if not mohid_utils.verify_run(output_file_name, ['Program Mohid Water successfully terminated',
                                                             'Program Mohid Land successfully terminated']):
                self.logger.info("MOHID RUN NOT SUCCESSFUL")
                raise ValueError("MOHID RUN NOT SUCCESSFUL")
            else:
                self.logger.info("MOHID RUN successful")

            #---------------------------------------------------------------------
            # opcçao com bypass para poupar tempo (run_mohidd = 0)
            #---------------------------------------------------------------------
            
            if run_mohidddc  == 1:

                self.logger.info("Starting MOHID_DDC")
            
                # DDC is run when an MPI run is done to join all the results into a single one.
                ddx_output_folder= Path(self.yaml['MOHID_WATER']['TREE_PATH'] + r"/DomainDecomposition_Logs/")
                
                if not os.path.isdir(ddx_output_folder):
                    os.makedirs(ddx_output_folder)
                    
                ddc_output_filename = Path(self.yaml['MOHID_WATER']['TREE_PATH'] + "/DomainDecomposition_Logs/" + "DomainDecomposition_" + self.current_initial_date.strftime("%Y-%m-%d") + ".log")
                mohid_ddc_output_log = open(ddc_output_filename, "w+")
                mohid_ddc_path = Path(self.yaml['MOHID_WATER']['TREE_PATH'] + mohid_ddc_exe)

                subprocess.run([mohid_ddc_path.__str__(), str(exe_path), "&"], cwd=os.path.dirname(self.yaml['MOHID_WATER']['TREE_PATH']),
                            stdout=mohid_ddc_output_log)
                mohid_ddc_output_log.close()
                
                if not mohid_utils.verify_run(ddc_output_filename, ["Program MohidDDC successfully terminated"]):
                    self.logger.info("MohidDDC NOT SUCCESSFUL")
                    raise ValueError("MohidDDC NOT SUCCESSFUL")
                else:
                    self.logger.info("MohidDDC successful")
        
        elif 'OPENMP' in self.yaml['MOHID_WATER'].keys() and self.yaml['MOHID_WATER']['OPENMP']['ENABLE']:

            self.logger.info("Starting MOHID OpenMP")
           
            if 'EXE_PATH' in self.yaml['MOHID_WATER']['OPENMP']:
                openmp_exe_path = Path(self.yaml['MOHID_WATER']['OPENMP']['EXE_PATH'])
            
            if openmp_exe_path.__str__() == "srun":
                subprocess.run([openmp_exe_path.__str__(), "-T", str(self.yaml['MOHID_WATER']['OPENMP']['TOTAL_PROCESSORS']),
                            str(exe_path), "&"], cwd=os.path.dirname(self.yaml['MOHID_WATER']['TREE_PATH']),
                            stdout=output_file)
                output_file.close()
                
            else:

                subprocess.run(str(exe_path), cwd=os.path.dirname(self.yaml['MOHID_WATER']['TREE_PATH']),
                                stdout=output_file)
                output_file.close()

                if not mohid_utils.verify_run(output_file_name, ['Program Mohid Water successfully terminated',
                                                                    'Program Mohid Land successfully terminated']):
                    self.logger.info("MOHID RUN NOT SUCCESSFUL")
                    raise ValueError("MOHID RUN NOT SUCCESSFUL")
                else:
                    self.logger.info("MOHID RUN successful")
                   
        else: # mohidwater

            self.logger.info("Starting MOHID run")
            # cwd is the working directory where the command will execute. stdout is the output file of the command
            # subprocess.run([str(exe_path), "&"], cwd=os.path.dirname(self.yaml['MOHID_WATER']['EXE_PATH']),
                            # stdout=output_file)
            subprocess.run(str(exe_path), cwd=os.path.dirname(self.yaml['MOHID_WATER']['TREE_PATH']),
                            stdout=output_file)
            output_file.close()

            if not mohid_utils.verify_run(output_file_name, ['Program Mohid Water successfully terminated',
                                                              'Program Mohid Land successfully terminated']):
                self.logger.info("MOHID RUN NOT SUCCESSFUL")
                raise ValueError("MOHID RUN NOT SUCCESSFUL")
            else:
                self.logger.info("MOHID RUN successful")


    def backup_decomposedfiles(self):
        """
        Back ups all the results located in the res/ folder of the project. It ignores all the results before consolidation
        (those that start with "MPI_"). Copies all the consolidated .hdf5 files to the Results_HDF/ folder in the backup path
        that the user defined. And the same goes for the Restart, TimeSeries and Discharges files.
        """
        
        main_path = Path(self.yaml['MOHID_WATER']['MAIN_PATH'])
        exe_path =  Path(self.yaml['MOHID_WATER']['EXE_PATH'])
        mohid_ddc_exe = "DomainDecompositionConsolidation.exe"

        for model in self.yaml['MOHID_WATER']['MODELS'].keys():
            model_keys = self.yaml['MOHID_WATER']['MODELS'][model].keys()
            results_path_end = Path(self.yaml['MOHID_WATER']['MODELS'][model]["PATH"] + "res/")
            results_path = main_path / results_path_end
           
            mpi_decomp_files = glob.glob(results_path.__str__() + r"/MPI*DecomposedFiles.dat")

            if len(mpi_decomp_files) > 0:

                self.logger.info("Backup of MPI*DecomposedFiles.dat")
  
                for filedec in mpi_decomp_files:
                   
                    # file_destination_partial = os.path.split(filedec)[1] + "x"                    
                    # file_destination = results_path / file_destination_partial

                    file_destination = filedec + "x"
                    
                    #self.logger.info("Backup decomposed Mpi_files: Copying " + str(filedec) + " to " + str(file_destination))
                    
                    copy(filedec, file_destination)
                    
                    with open(file_destination, "r") as file:
                        file_lines = file.readlines()
                        number_of_lines = len(file_lines)
                        
                        filex = ""
                        n=0
                        
                        #apenas faz o consolidation dos .fin files para poder continuar o run
                        for n in range(number_of_lines):
                            line = file_lines[n]        
                            
                            if re.search(".fin", line):
                                filex = filex + line
                            elif re.search(".fin5", line):
                                 filex = filex + line
                        
                        with open(filedec,"w") as filedat:
                            filedat.write(filex)

          
            # DDC is ran when an MPI run is done to join all the results into a single one.
            ddx_output_folder= Path(self.yaml['MOHID_WATER']['TREE_PATH'] + r"/DomainDecomposition_Logs/")
            if not os.path.isdir(ddx_output_folder):
                os.makedirs(ddx_output_folder)
                
            ddc_output_filename = Path(self.yaml['MOHID_WATER']['TREE_PATH'] + "/DomainDecomposition_Logs/" + "DomainDecomposition_" + self.current_initial_date.strftime("%Y-%m-%d") + ".log")
            mohid_ddc_output_log = open(ddc_output_filename, "w+")

            if 'MPI' in self.yaml['MOHID_WATER'].keys() and self.yaml['MOHID_WATER']['MPI']['ENABLE']:
                if 'MOHID_CONSOLIDATION_EXE' in self.yaml['MOHID_WATER']['MPI']:
                    mohid_ddc_exe = self.yaml['MOHID_WATER']['MPI']['MOHID_CONSOLIDATION_EXE']
            
            mohid_ddc_path = Path(self.yaml['MOHID_WATER']['TREE_PATH'] + mohid_ddc_exe)
               
            subprocess.run([mohid_ddc_path.__str__(), str(exe_path), "&"], cwd=os.path.dirname(self.yaml['MOHID_WATER']['TREE_PATH']),
                            stdout=mohid_ddc_output_log)
            mohid_ddc_output_log.close()
            
            if not mohid_utils.verify_run(ddc_output_filename, ["Program MohidDDC successfully terminated"]):
                self.logger.info("MohidDDC NOT SUCCESSFUL")
                raise ValueError("MohidDDC NOT SUCCESSFUL")
            else:
                self.logger.info("MohidDDC successful")

            #rename de novo das files .datx para .dat novamente
            
            if len(mpi_decomp_files) > 0:
                
                for filedec in mpi_decomp_files:

                    file_origin = filedec + "x"

                    # tirar os .fin dos ficheiros .dat pois já foram criados na continuacao de calculo

                    file_lines=""

                    with open(file_origin, "r") as file:

                        file_lines = file.readlines()
                        number_of_lines = len(file_lines)
                        filex = ""
                        nx=0
                        #apenas faz o consolidation dos .fin files para poder continuar o run
                        for nx in range(number_of_lines):
                            line = file_lines[nx]        
                            if re.search(".hdf5", line):
                                filex = filex + line
                            elif re.search(".hdf", line):
                                 filex = filex + line

                        with open(filedec,"w") as filedat:
                            filedat.write(filex)
 #                   copy(file_origin, filedec)


    '''
    MOHID needs the file model.dat to be changed, especially START and END times.
    This function changes that file in each iteration to update START and END and other parameters that can be defined
    in the yaml config file.
    It receives the yaml object and the 'model' dictionary which is in 'mohidwater' dictionary.
    '''

    def change_model_dat(self, model, main_path: Path):
        self.logger.info("Creating new model file for model: " + model['NAME'])
        keys = model.keys()
        path = main_path / model['PATH'] / "data/"
        path = path.expanduser()
        if not os.path.isdir(path):
            self.logger.info("Path for model folder does not exist.")
            self.logger.info("Check path parameters in the yaml file. Exiting ART.")
            raise ValueError("Path for model folder does not exist.")

        file_path = Path(path, "Model_1.dat")
        
        if not file_path.is_file():
            raise ValueError("File " + str(file_path) + " does not exist.")
        
        file_modifier.modify_start_dat_date(file_path, file_modifier.date_to_mohid_date(self.current_initial_date), self.logger)
        self.logger.info("Changed START of " + str(file_path) + " to " +
                         file_modifier.date_to_mohid_date(self.current_initial_date))
        file_modifier.modify_end_dat_date(file_path, file_modifier.date_to_mohid_date(self.current_final_date), self.logger)
        self.logger.info("Changed END of " + str(file_path) + " to " +
                         file_modifier.date_to_mohid_date(self.current_final_date))
        file_modifier.modify_line(file_path, "DT", str(model['DT']), self.logger)
        if 'OPENMP' in self.yaml['MOHID_WATER'].keys() and self.yaml['MOHID_WATER']['OPENMP']['ENABLE']:
            if 'TOTAL_PROCESSORS' in self.yaml['MOHID_WATER']['OPENMP']:
                num_omp_processors = self.yaml['MOHID_WATER']['OPENMP']['TOTAL_PROCESSORS']
            else:
                self.logger.info("NUM_PROCESSORS not defined. model will use max threads available")
                num_omp_processors = multiprocessing.cpu_count()
            file_modifier.modify_line(file_path, "OPENMP_NUM_THREADS", str(num_omp_processors), self.logger)
            
        if 'mohidwater.dat' in keys:
            for key in model['mohidwater.dat'].keys():
                file_modifier.modify_line(file_path, key, model['mohidwater.dat'][key], self.logger)
        self.logger.info("Model " + model['NAME'] + " .dat file was created.")
        return

 
    def gather_restart_files(self, model: dict, main_path:Path):
        """
        Gets restart files from previous run. These files need to be put in /res folder of the project you're trying to
        run.
        """
        self.logger.info("Gathering the restart files for model: " + model['NAME'])
        
        filename = "%Y-%m-%d"
        if 'dateFormat' in self.yaml['MOHID_WATER'].keys():
            filename = self.yaml['MOHID_WATER']['filename']

        previous_init_date = self.current_initial_date - datetime.timedelta(days=1)
        previous_final_date = previous_init_date + datetime.timedelta(days=self.yaml['SIMULATION']['DAYS_PER_RUN'])
        self.logger.info("Restart Files Initial Day: " + previous_init_date.strftime(filename))
        self.logger.info("Restart Files Final Day: " + previous_final_date.strftime(filename))

        base_fin_path = Path(model['STORAGE_PATH'])
        date_fin_path = "Restart/" + previous_init_date.strftime(filename) + "_" + \
                        previous_final_date.strftime(filename) + "/"
        path_fin_files = base_fin_path / date_fin_path
      
        self.logger.info("Source Restart Files: " + path_fin_files.__str__())

        if not os.path.isdir(path_fin_files):
            self.logger.info("Restart folder " + path_fin_files.__str__() + "does not exist.")
            return

        restart_model_path = model['PATH'] + "res/"
        restart_files_dest = main_path / restart_model_path
        if not os.path.isdir(restart_files_dest):
            os.makedirs(restart_files_dest)

        # glob creates a list with all files that match the regex expression
        fin_files = glob.glob(path_fin_files.__str__() + r"/*.fin")
        fin5_files = glob.glob(path_fin_files.__str__() + r"/*.fin5")
        for file in fin_files:
            # the nomfich.dat file for mohidwater is not changed and when a restart file is generated it ends with _1.fin
            # and because of that an input restart file needs to finish with _0.fin. So we simply change it when we copy it.
            file_destination_partial = os.path.split(file)[1].split("_")[0] + "_0.fin"
            file_destination = restart_files_dest / file_destination_partial
            self.logger.info("Restart Files: Copying " + str(file) + " to " + str(file_destination))
            copy(file, file_destination)
        for file in fin5_files:
            file_destination_partial = os.path.split(file)[1].split("_")[0] + "_0.fin5"
            file_destination = restart_files_dest / file_destination_partial
            self.logger.info("Restart Files: Copying " + str(file) + " to " + str(file_destination))
            copy(file, file_destination)


    def check_triggers(self, repeat_index: int, days_per_run: int):
        """ Receives a yaml config file with only the trigger subtree and checks the trigger entries for correct
        configuration. Checks for dependencies within the models. The execution is never interrupted by this function,
        any errors found are reported in the logger.
        """
        if 'TRIGGER' in self.yaml and self.yaml['TRIGGER']['ENABLE']:
            trigger_config = self.yaml['TRIGGER']
            if 'CHECK_ALL' in trigger_config:
                check = trigger_config['CHECK_ALL']
            else:
                check = True

            if repeat_index == 0 or check:

                if 'FOLDERS_TO_WATCH' in trigger_config:
                    folders = trigger_config['FOLDERS_TO_WATCH']
                else:
                    folders = None
                    self.logger.info("No folders to watch on triggers FOLDER_TO_WATCH parameter is empty.")
                    

                if 'TRIGGER_MAX_WAIT' in trigger_config:
                    timer = trigger_config['TRIGGER_MAX_WAIT'] * 3600
                else:
                    timer = static.DEFAULT_MAX_WAIT * 3600
                    self.logger.info(
                        "No waiting time on triggers TRIGGER_MAX_WAIT parameter is empty. Assigning default "
                        "max wait time of 6 hours.")

                if 'TRIGGER_POLLING_RATE' in trigger_config:
                    rate = trigger_config['TRIGGER_POLLING_RATE']
                else:
                    rate = static.DEFAULT_POLLING_RATE
                    self.logger.info(
                        "No polling rate on triggers. TRIGGER_POLLING_RATE is empty. Assigning "
                        "default polling rate of 120 seconds.")
                filename = "%Y-%m-%d"
                initial_date = self.current_initial_date.strftime(filename)
                tmp_date = self.current_initial_date + datetime.timedelta(days_per_run)
                final_date = tmp_date.strftime(filename)
                if folders:
                    for folder in folders:
                        file = folder + initial_date + "_" + final_date + ".dat"
                        while not os.path.exists(file):
                            self.logger.info("Waiting for Trigger file to be created in watch folder")
                            time.sleep(rate)
                            timer = timer - rate
                            if timer < 0:
                                self.logger.info("Reached max waiting time while trying to find file " + str(file) + ". Resuming \
                                 execution without the file...")
                                return

                        finished = False
                        self.logger.info("Checking Trigger file status - will advance when becomes Finished")
                        while not finished:
                            f = open(file, 'r')
                            for line in f.readlines():
                                if line.startswith("STATUS"):
                                    if "FINISHED" in line:
                                        finished = True
                                        self.logger.info("File " + str(file) + " found with status FINISHED.")
                            f.close()
                            if not finished:
                                time.sleep(
                                    rate * 2)  # rate is doubled to prevent file error with several opens and closes
                                timer = timer - rate * 2
                                if timer < 0:
                                    self.logger.info("Reached max waiting time while waiting for file " + file + " to change \
                                     status to finished. Resuming execution without the correct status on this file...")
                                    return

    def write_trigger(self, main_path: Path, days_per_run, stage):
        """ Receives a yaml config file with only the trigger subtree and writes the trigger file.
        The execution is never interrupted by this function, any errors found are reported in the logger.
        """
        if 'TRIGGER' in self.yaml and self.yaml['TRIGGER']['ENABLE']:
            trigger_config = self.yaml['TRIGGER']
            if 'WRITE_TRIGGER' in trigger_config and trigger_config['WRITE_TRIGGER']:
                output_trigger = trigger_config['WRITE_TRIGGER']
                dest_folder = Path(main_path + r"/Logs/Triggers/")
                if not os.path.isdir(dest_folder):
                    os.makedirs(dest_folder)
            else:
                output_trigger = False
                self.logger.info("Output trigger not set. WRITE_TRIGGER parameter is empty.")

            if output_trigger:
                filename = "%Y-%m-%d"
                initial_date = self.current_initial_date.strftime(filename)
                tmp_date = self.current_initial_date + datetime.timedelta(days_per_run)
                final_date = tmp_date.strftime(filename)
                filename = initial_date + "_" + final_date + ".dat"
                filepath = Path(dest_folder / filename)

                now = datetime.datetime.now()
                system_time = now.strftime("%Y-%m-%d %H:%M")

                file = open(filepath, 'w')
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
                file.write(
                    'START                         : ' + file_modifier.date_to_mohid_date(self.current_initial_date))
                file.write('\n')
                file.write(
                    'END                           : ' + file_modifier.date_to_mohid_date(self.current_final_date))
                file.write('\n')

                if stage == "Running":
                    file.write('STATUS                        : RUNNING')
                elif stage == "Finished":
                    file.write('STATUS                        : FINISHED')

                file.write('\n')
                file.write('SYSTEM TIME                   : ' + system_time)
                file.close()

    def backup_simulation(self):
        """
        Back ups all the results located in the res/ folder of the project. It ignores all the results before consolidation
        (those that start with "MPI_"). Copies all the consolidated .hdf5 files to the Results_HDF/ folder in the backup path
        that the user defined. And the same goes for the Restart, TimeSeries and Discharges files.
        """
        run_mohidddc = 1

        filename = "%Y-%m-%d"
        if 'filename' in self.yaml['MOHID_WATER'].keys():
            filename = self.yaml['MOHID_WATER']['filename']

        initial_date = self.current_initial_date.strftime(filename)
        tmp_date = self.current_initial_date + datetime.timedelta(self.yaml['SIMULATION']['DAYS_PER_RUN'])
        final_date = tmp_date.strftime(filename)

        main_path = Path(self.yaml['MOHID_WATER']['MAIN_PATH'])
        self.logger.info("Simulation Results Initial Date: " + initial_date)
        self.logger.info("Simulation Results Final Date: " + final_date)

        if 'MPI' in self.yaml['MOHID_WATER'].keys() and self.yaml['MOHID_WATER']['MPI']['ENABLE']:
            if 'RUN_MOHID_CONSOLIDATION' in self.yaml['MOHID_WATER']['MPI']:
                run_mohidddc = self.yaml['MOHID_WATER']['MPI']['RUN_MOHID_CONSOLIDATION']

        if run_mohidddc == 0: 
           
            for model in self.yaml['MOHID_WATER']['MODELS'].keys():
                model_keys = self.yaml['MOHID_WATER']['MODELS'][model].keys()
                results_path_end = Path(self.yaml['MOHID_WATER']['MODELS'][model]["PATH"] + "res/")
                results_path = main_path / results_path_end

                generic_path = Path(self.yaml['MOHID_WATER']['MODELS'][model]['STORAGE_PATH'])
                date_path = initial_date + "_" + final_date + "/"
                restart_storage = generic_path / "Restart/" / date_path
                results_storage = generic_path / "Results_HDF/" / date_path
                
                results_mpi_storage = generic_path / "Results_MPI/" / date_path / "res/"
                time_series_storage = generic_path / "Results_TimeSeries/" / date_path
                discharges_storage = generic_path / "Discharges/" / date_path
                
                # ------------  .fin files -------------------------------------------

                if 'HAS_SOLUTION_FROM_FILE' not in model_keys or not self.yaml['MOHID_WATER']['MODELS'][model]['HAS_SOLUTION_FROM_FILE']:
                    fin_files = glob.glob(results_path.__str__() + r"/*_1.fin")
                    fin5_files = glob.glob(results_path.__str__() + r"/*_1.fin5")
                    fin_files = fin5_files + fin_files
                    if len(fin_files) > 0:
                        if not os.path.isdir(restart_storage):
                            os.makedirs(restart_storage)
                        for file in fin_files:
                            if os.path.split(file)[1].startswith("MPI"):
                                continue
                            file_destination = restart_storage / os.path.split(file)[1]
                            self.logger.info("Backup Simulation Fin_files: Copying " + str(file) + " to " + str(file_destination))
                            copy(file, file_destination)
                
                # ------------  .MPI files -------------------------------------------

                mpi_files = glob.glob(results_path.__str__() + r"/MPI*")
                if len(mpi_files) > 0:
                   
                    if not os.path.isdir(results_mpi_storage):
                        os.makedirs(results_mpi_storage)

                    for file in mpi_files:
                        file_destination =  results_mpi_storage / os.path.split(file)[1]
    
                        try:
                            copy(file, file_destination)
                            self.logger.info("Backup MPI decomposed Files: Copying  " + str(file) + " to " + str(file_destination))
                        except IOError as e:
                            self.logger.error("Backup MPI decomposed Files NOT SUCCESSFUL")
                            raise ValueError("Backup MPI decomposed Files NOT SUCCESSFU") 
                            
                    tree_file = Path(self.yaml['MOHID_WATER']['TREE_PATH'] + r"/Tree.dat")
                    file_destination = results_mpi_storage /  "Tree.dat"
                    
                    try:
                        copy(tree_file, file_destination)
                        self.logger.info("Tree File: Copying to " + str(file_destination))
                    except IOError as e:
                        self.logger.error("Error copying the Tree File")
                        raise ValueError("Error copying the Tree File") 
                                       
            
            # ---------------  Time series-------------------------------------

            time_series_files = glob.glob(results_path.__str__() + r"/Run1/*.*")
           
            if len(time_series_files) > 0:
                print(str(time_series_storage))
                if not os.path.isdir(time_series_storage):
                    os.makedirs(time_series_storage)
                for file in time_series_files:
                    file_destination = time_series_storage / os.path.split(file)[1]
                    self.logger.info("Backup Simulation TimeSerie Files: Copying " + str(file) + " to " + str(file_destination))
                    copy(file, file_destination)

        else: #run_mohidddc = 1

            for model in self.yaml['MOHID_WATER']['MODELS'].keys():
                model_keys = self.yaml['MOHID_WATER']['MODELS'][model].keys()
                results_path_end = Path(self.yaml['MOHID_WATER']['MODELS'][model]["PATH"] + "res/")
                results_path = main_path / results_path_end

                generic_path = Path(self.yaml['MOHID_WATER']['MODELS'][model]['STORAGE_PATH'])
                date_path = initial_date + "_" + final_date + "/"
                restart_storage = generic_path / "Restart/" / date_path
                results_storage = generic_path / "Results_HDF/" / date_path
                time_series_storage = generic_path / "Results_TimeSeries/" / date_path
                discharges_storage = generic_path / "Discharges/" / date_path
                
                # ------------  .fin files -------------------------------------------

                if 'HAS_SOLUTION_FROM_FILE' not in model_keys or not self.yaml['MOHID_WATER']['MODELS'][model]['HAS_SOLUTION_FROM_FILE']:
                    fin_files = glob.glob(results_path.__str__() + r"/*_1.fin")
                    fin5_files = glob.glob(results_path.__str__() + r"/*_1.fin5")
                    fin_files = fin5_files + fin_files
                    if len(fin_files) > 0:
                        if not os.path.isdir(restart_storage):
                            os.makedirs(restart_storage)
                        for file in fin_files:
                            if os.path.split(file)[1].startswith("MPI"):
                                continue
                            file_destination = restart_storage / os.path.split(file)[1]
                            self.logger.info("Backup Simulation Fin_files: Copying " + str(file) + " to " + str(file_destination))
                            copy(file, file_destination)
                
                # ------------  .HDF5 files -------------------------------------------
                
                hdf5_files = glob.glob(results_path.__str__() + r"/*.hdf5")
                if len(hdf5_files) > 0:
                    if not os.path.isdir(results_storage):
                        os.makedirs(results_storage)

                    # only backup specific result files
                    if 'RESULTS_LIST' in model_keys:
                        for file in hdf5_files:
                            if os.path.split(file)[1].startswith("MPI"):
                                continue
                            file_name = os.path.split(file)[1]
                            name_array = file_name.split("_")
                            if len(name_array) > 2:
                                # Hydrodynamic_1_Surface becomes Hydrodynamic_Surface
                                file_name_copy = name_array[0] + "_" + name_array[2]
                            else:
                                file_type = name_array[-1].split(".")[1]
                                file_name_copy = name_array[0] + "." + file_type

                            # if the file_name is not in the RESULTS_LIST it will be ignored
                            if file_name not in self.yaml['MOHID_WATER']['MODELS'][model]['RESULTS_LIST']:
                                continue

                            file_destination = results_storage / file_name_copy
                            self.logger.info("Backup Simulation HDF Files: Copying " + str(file) + " to " + str(file_destination))
                            copy(file, file_destination)

                    # defaults to backup all results files
                    else:
                        for file in hdf5_files:
                            if os.path.split(file)[1].startswith("MPI"):
                                continue

                            file_name = os.path.split(file)
                            name_array = file_name.split("_")
                            if name_array > 2:
                                # Hydrodynamic_1_Surface becomes Hydrodynamic_Surface
                                file_name = name_array[0] + "_" + name_array[2]
                            else:
                                file_type = name_array[-1].split(".")[1]
                                file_name = name_array[0] + "." + file_type
                            file_destination = results_storage / file_name
                            self.logger.info("Backup Simulation HDF Files: Copying " + str(file) + " to " + str(file_destination))

                            copy(file, file_destination)

            # ---------------  Time series-------------------------------------

            time_series_files = glob.glob(results_path.__str__() + r"/Run1/*.*")
           
            if len(time_series_files) > 0:
                print(str(time_series_storage))
                if not os.path.isdir(time_series_storage):
                    os.makedirs(time_series_storage)
        
                for file in time_series_files:
                    file_destination = time_series_storage / os.path.split(file)[1]
                    self.logger.info("Backup Simulation TimeSerie Files: Copying " + str(file) + " to " + str(file_destination))
                    copy(file, file_destination)
