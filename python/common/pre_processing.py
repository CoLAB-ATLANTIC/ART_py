import subprocess
# import mohid.util.file_modifier as file_modifier
import utils.file_modifier as file_modifier
import os
from pathlib import Path

# import mohid.util.constants as static
import utils.constants as static
import datetime
import time
# import mohid.util.mohid_utils as mohid_utils
import utils.mohid_utils as mohid_utils
from common.trigger import Trigger


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

def execute(yaml, logger, current_initial_date, current_final_date,repeat_index):
    
    for block in yaml['PRE_PROCESSING']:
        block_keys = yaml['PRE_PROCESSING'][block].keys()
        block_dict = yaml['PRE_PROCESSING'][block]

        if 'RUN' in block_keys and block_dict['RUN']:

            days_per_run = yaml['SIMULATION']['DAYS_PER_RUN']

            # Trigger logic execution per sub-tool
            trigger = Trigger(yaml, logger, block)
            trigger.check(repeat_index, current_initial_date)
            trigger.check_condition(current_initial_date, current_final_date)

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
                    trigger.write(current_initial_date, current_final_date, status="Running")
                    
                    logger.info(PRE_PROCESSING_STRING + block_dict['EXE_PATH'])
                    subprocess.run(run_array, cwd=os.path.dirname(block_dict['FLAGS']))
                    
                    if check_log == True:
                        status_stop=open_log(filename_check)
                        if status_stop == True:
                            logger.info(PRE_PROCESSING_STRING + "NOT SUCCESSFULL " + block)
                        else:
                            trigger.write(current_initial_date, current_final_date, status="Finished")
                    else:
                        trigger.write(current_initial_date, current_final_date, status="Finished")
    
            else:
                if 'OUTPUT_TO_FILE' in block_keys and block_dict['OUTPUT_TO_FILE']:
                    with open(block_dict['OUTPUT_FILEPATH'], 'w') as log:
                        
                        #write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, status="Running")
                        # trigger.write(current_initial_date, current_final_date, status="Running")

                        logger.info(PRE_PROCESSING_STRING + block_dict['EXE_PATH'])
                        subprocess.run(block_dict['EXE_PATH'], stdout=log, cwd=os.path.dirname(block_dict['EXE_PATH']))
                        log.close()

                    if check_log == True:
                        status_stop=open_log(filename_check)
                        if status_stop == True:
                            logger.info(PRE_PROCESSING_STRING + "NOT SUCCESSFULL " + block)
                        else:
                            # write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, status="Finished")
                            trigger.write(current_initial_date, current_final_date, status="Finished")
                    else:
                        # write_trigger(yaml, logger, block, days_per_run,current_initial_date,current_final_date, status="Finished")
                        trigger.write(current_initial_date, current_final_date, status="Finished")
                else:
                    # trigger for running status before executing the sub-tool
                    trigger.write(current_initial_date, current_final_date, status="Running")

                    logger.info(PRE_PROCESSING_STRING + block_dict['EXE_PATH'])
                    subprocess.run(block_dict['EXE_PATH'], cwd=os.path.dirname(block_dict['EXE_PATH']))
                    
                    if check_log == True:
                        status_stop=open_log(filename_check)
                        if status_stop == True:
                            logger.info(PRE_PROCESSING_STRING + "NOT SUCCESSFULL " + block)
                        else:
                            trigger.write(current_initial_date, current_final_date, status="Finished")
                    else:
                        # trigger for running status after executing the sub-tool
                        trigger.write(current_initial_date, current_final_date, status="Finished")                    
    return