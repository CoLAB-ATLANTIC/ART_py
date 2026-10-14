import subprocess
import mohid.util.file_modifier as file_modifier
import os
from pathlib import Path

import mohid.util.constants as static
import datetime
import time
import mohid.util.mohid_utils as mohid_utils


PRE_PROCESSING_STRING = "Executing PRE Processing module: "

def open_log(filename):
    status_stop = False
    f = open(filename, 'r')
    for line in f.readlines():
        if "NOT SUCCESSFULL" in line:
            status_stop = True
            return (status_stop)
    f.close()

def dat_date_change(file_path, logger, current_initial_date, current_final_date):
    file_modifier.modify_start_dat_date(file_path, file_modifier.date_to_mohid_date(current_initial_date), logger)
    file_modifier.modify_end_dat_date(file_path, file_modifier.date_to_mohid_date(current_final_date), logger)

def execute(yaml, logger, current_initial_date, current_final_date,days_run):
    
    for block in yaml['PRE_PROCESSING']:
        block_keys = yaml['PRE_PROCESSING'][block].keys()
        block_dict = yaml['PRE_PROCESSING'][block]

        if 'RUN' in block_keys and block_dict['RUN']:

            days_per_run = yaml['SIMULATION']['DAYS_PER_RUN']

            check_triggers(yaml, logger, block, days_run, current_initial_date)

            check_log=False
            if 'LOGFILE_CHECK' in block_keys and block_dict['LOGFILE_CHECK']:
                check_log=True
                filename_aux= str(block_dict['LOGFILE_CHECK'])
                filename_check= mohid_utils.create_file_name_with_date(filename_aux, current_initial_date, current_final_date)

            if 'DAT_DATE_CHANGE' in block_keys and block_dict['DAT_DATE_CHANGE']:
                dat_date_change(Path(block_dict['CONFIG_FILEPATH']), logger, current_initial_date, current_final_date)
            if 'FLAGS' in block_keys:
                flags_array = block_dict['FLAGS'].split(" ")
                run_array = [block_dict['EXE_PATH']] + flags_array
                if 'OUTPUT_TO_FILE' in block_keys and block_dict['OUTPUT_TO_FILE']:
                    with open(block_dict['OUTPUT_FILEPATH'], 'w') as log:
                        subprocess.run(run_array, stdout=log, cwd=os.path.dirname(block_dict['EXE_PATH']))
                        log.close()
                else:

                    # write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, stage="Running")
                    
                    logger.info(PRE_PROCESSING_STRING + block_dict['EXE_PATH'])
                    subprocess.run(run_array, cwd=os.path.dirname(block_dict['FLAGS']))
                    
                    if check_log == True:
                        status_stop=open_log(filename_check)
                        if status_stop == True:
                            logger.info(PRE_PROCESSING_STRING + "NOT SUCCESSFULL " + block)
                        else:
                            pass
                            # write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, stage="Finished")
                    else:
                        pass
                        # write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, stage="Finished")
    
            else:
                if 'OUTPUT_TO_FILE' in block_keys and block_dict['OUTPUT_TO_FILE']:
                    with open(block_dict['OUTPUT_FILEPATH'], 'w') as log:
                        
                        #write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, stage="Running")

                        logger.info(PRE_PROCESSING_STRING + block_dict['EXE_PATH'])
                        subprocess.run(block_dict['EXE_PATH'], stdout=log, cwd=os.path.dirname(block_dict['EXE_PATH']))
                        log.close()

                    if check_log == True:
                        status_stop=open_log(filename_check)
                        if status_stop == True:
                            logger.info(PRE_PROCESSING_STRING + "NOT SUCCESSFULL " + block)
                        else:
                            write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, stage="Finished")
                    else:
                        write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, stage="Finished")
                else:
                    #write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, stage="Running")

                    logger.info(PRE_PROCESSING_STRING + block_dict['EXE_PATH'])
                    subprocess.run(block_dict['EXE_PATH'], cwd=os.path.dirname(block_dict['EXE_PATH']))
                    
                    if check_log == True:
                        status_stop=open_log(filename_check)
                        if status_stop == True:
                            logger.info(PRE_PROCESSING_STRING + "NOT SUCCESSFULL " + block)
                        else:
                            write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, stage="Finished")
                    else:
                        pass
                        #write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, stage="Finished")
                    
    return



def check_triggers(yaml,logger, block, days_run, current_initial_date):
                     
        """ Receives a yaml config file with only the trigger subtree and checks the trigger entries for correct
        configuration. Checks for dependencies within the models. The execution is never interrupted by this function,
        any errors found are reported in the logger.
        """

        if 'TRIGGER' in yaml['PRE_PROCESSING'][block] and yaml['PRE_PROCESSING'][block]['TRIGGER']['ENABLE']:
            trigger_config = yaml['PRE_PROCESSING'][block]['TRIGGER']

            check = False
            days_per_run = yaml['SIMULATION']['DAYS_PER_RUN']
            
            # alterar aqui - Assume por defeito que o check é true. Assumimos que por defeito check = false
            
            if 'CHECK_ALL' in trigger_config:
                check = trigger_config['CHECK_ALL']
            # else:
            #     check = True
            # alterar aqui tb

            if check:
                #if days_run == 0 or check:   ?????? ver esta questão
                if days_run == 0 :

                    if 'FOLDERS_TO_WATCH' in trigger_config:
                        folders = trigger_config['FOLDERS_TO_WATCH']
                    else:
                        folders = None
                        logger.info("No folders to watch on triggers FOLDER_TO_WATCH parameter is empty.")
                        
                    if 'TRIGGER_MAX_WAIT' in trigger_config:
                        timer = trigger_config['TRIGGER_MAX_WAIT'] * 3600
                    else:
                        timer = static.DEFAULT_MAX_WAIT * 3600
                        logger.info(
                            "No waiting time on triggers TRIGGER_MAX_WAIT parameter is empty. Assigning default "
                            "max wait time of 6 hours.")

                    if 'TRIGGER_POLLING_RATE' in trigger_config:
                        rate = trigger_config['TRIGGER_POLLING_RATE']
                    else:
                        rate = static.DEFAULT_POLLING_RATE
                        logger.info(
                            "No polling rate on triggers. TRIGGER_POLLING_RATE is empty. Assigning "
                            "default polling rate of 120 seconds.")
                    
                    filename = "%Y-%m-%d"
                    
                    initial_date = current_initial_date.strftime(filename)
                    tmp_date = current_initial_date + datetime.timedelta(days_per_run)
                    final_date = tmp_date.strftime(filename)
    
                    if folders:
                        for folder in folders:

                            file = folder + initial_date + "_" + final_date + ".dat"
                            
                            while not os.path.exists(file):
                                logger.info("Waiting for Trigger file to be created in watch folder")
                                time.sleep(rate)
                                timer = timer - rate
                                if timer < 0:
                                    logger.info("Reached max waiting time while trying to find file " + str(file) + ". Resuming \
                                    execution without the file...")
                                    return

                            finished = False
                            logger.info("Checking Trigger file status - will advance when becomes Finished")
                            while not finished:
                                f = open(file, 'r')
                                for line in f.readlines():
                                    if line.startswith("STATUS"):
                                        if "FINISHED" in line:
                                            finished = True
                                            logger.info("File " + str(file) + " found with status FINISHED.")
                                f.close()
                                if not finished:
                                    time.sleep(
                                        rate * 2)  # rate is doubled to prevent file error with several opens and closes
                                    timer = timer - rate * 2
                                    if timer < 0:
                                        logger.info("Reached max waiting time while waiting for file " + file + " to change \
                                        status to finished. Resuming execution without the correct status on this file...")
                                        return
                                
def write_trigger(yaml, logger, block, days_per_run, current_initial_date,current_final_date,stage):
        
        """ Receives a yaml config file with only the trigger subtree and writes the trigger file.
        The execution is never interrupted by this function, any errors found are reported in the logger.
        """

        main_path = yaml['MOHID_WATER']['MAIN_PATH']
        path_trigger = Path(main_path + r"/Logs/Triggers/" + block + r"/") 

        if 'TRIGGER' in yaml['PRE_PROCESSING'][block] and yaml['PRE_PROCESSING'][block]['TRIGGER']['ENABLE']:
            trigger_config = yaml['PRE_PROCESSING'][block]['TRIGGER']
          
            if 'WRITE_TRIGGER' in trigger_config and trigger_config['WRITE_TRIGGER']:
                output_trigger = trigger_config['WRITE_TRIGGER']
                dest_folder = path_trigger
                if not os.path.isdir(dest_folder):
                    os.makedirs(dest_folder)
            else:
                output_trigger = False
                logger.info("Output trigger not set. WRITE_TRIGGER parameter is empty.")

            if output_trigger:
                filename = "%Y-%m-%d"
                initial_date = current_initial_date.strftime(filename)
                tmp_date = current_initial_date + datetime.timedelta(days_per_run)
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
                    file.write(block + ' is running for the following period:')
                elif stage == "Finished":
                    file.write(block + ' finished for the following period:')

                file.write('\n')
                file.write(
                    'START                         : ' + file_modifier.date_to_mohid_date(current_initial_date))
                file.write('\n')
                file.write(
                    'END                           : ' + file_modifier.date_to_mohid_date(current_final_date))
                file.write('\n')

                if stage == "Running":
                    file.write('STATUS                        : RUNNING')
                elif stage == "Finished":
                    file.write('STATUS                        : FINISHED')

                file.write('\n')
                file.write('SYSTEM TIME                   : ' + system_time)
                file.close()
                                                