import os
import sys
import datetime
import time
import subprocess
from pathlib import Path

# import mohid.util.file_modifier as file_modifier
import utils.file_modifier as file_modifier
# import mohid.util.constants as static
import utils.constants as static


class TriggerConditionNotMet(ValueError):
    """ Raised when the condition script of a trigger evaluates to false. Subclasses ValueError so ART's
    error routine (log, email, exit) stops the whole run.
    """


class Trigger:
    """ Handles the trigger files of a processing block: checking the triggers of the blocks it depends on and
    writing its own trigger file. The execution is never interrupted by this class, any errors found are reported
    in the logger.
    """

    DATE_FORMAT = "%Y-%m-%d"

    def __init__(self, yaml, logger, block, section='PRE_PROCESSING'):
        self.yaml = yaml
        self.logger = logger
        self.block = block
        self.days_per_run = yaml['SIMULATION']['DAYS_PER_RUN']

        block_dict = yaml[section][block]
        self.enabled = 'TRIGGER' in block_dict and block_dict['TRIGGER']['ENABLE']
        self.config = block_dict['TRIGGER'] if self.enabled else {}

    def _file_name(self, current_initial_date):
        initial_date = current_initial_date.strftime(self.DATE_FORMAT)
        tmp_date = current_initial_date + datetime.timedelta(self.days_per_run)
        final_date = tmp_date.strftime(self.DATE_FORMAT)
        return initial_date + "_" + final_date + ".dat"

    def check(self, repeat_index, current_initial_date):
        """ Checks the trigger entries for correct configuration and waits for the trigger files of the
        dependencies to be FINISHED.
        """

        if not self.enabled:
            return

        # Assumimos que por defeito check = false
        check = self.config.get('CHECK_ALL', False)

        if not check or repeat_index != 0:
            return

        if 'FOLDERS_TO_WATCH' in self.config:
            folders = self.config['FOLDERS_TO_WATCH']
            for folder in folders:
                if not os.path.isdir(folder):
                    self.logger.info(f"Folder {folder} does not exist. Please check the FOLDERS_TO_WATCH parameter in the trigger configuration.")

        else:
            folders = None
            self.logger.info("No folders to watch on triggers FOLDER_TO_WATCH parameter is empty.")


        if 'TRIGGER_MAX_WAIT_H' in self.config:
            timer = self.config['TRIGGER_MAX_WAIT_H'] * 3600
        else:
            timer = static.DEFAULT_MAX_WAIT_H * 3600
            self.logger.info(
                "No waiting time on triggers TRIGGER_MAX_WAIT_H parameter is empty. Assigning default "
                "max wait time of 6 hours.")

        if 'TRIGGER_POLLING_RATE' in self.config:
            pooling_rate = self.config['TRIGGER_POLLING_RATE_S']
        else:
            pooling_rate = static.DEFAULT_POLLING_RATE_S
            self.logger.info(
                "No polling rate on triggers. TRIGGER_POLLING_RATE_S is empty. Assigning "
                "default polling rate of 120 seconds.")

        if not folders:
            return

        filename = self._file_name(current_initial_date)

        for folder in folders: # allows concurrence of several folders to be watched for triggers

            file = folder + filename # parent directory has to follow same temporal resolution

            while not os.path.exists(file):
                self.logger.info("Waiting for Trigger file to be created in watch folder")
                time.sleep(pooling_rate)
                timer = timer - pooling_rate
                if timer < 0:
                    self.logger.info("Reached max waiting time while trying to find file " + str(file) +
                                     ". Resuming execution without the file...")
                    return

            finished = False
            self.logger.info("Checking Trigger file status - will advance when becomes Finished")
            while not finished:
                with open(file, 'r') as f:
                    for line in f.readlines():
                        if line.startswith("STATUS") and "FINISHED" in line:
                            finished = True
                            self.logger.info("File " + str(file) + " found with status FINISHED.")
                if not finished:
                    time.sleep(pooling_rate * 2)  # pooling_rate is doubled to prevent file error with several opens and closes
                    timer = timer - (pooling_rate * 2)
                    if timer < 0:
                        self.logger.info("Reached max waiting time while waiting for file " + file + " to change "
                                         "status to finished. Resuming execution without the correct status on "
                                         "this file...")
                        return

    def check_condition(self, current_initial_date, current_final_date):
        """ Runs the condition script with its .dat configuration file. The script receives the .dat path as its
        only argument and must print True or False as the last line of its output. False stops the whole
        execution; a script that crashes (non-zero exit code) or prints anything else is reported as an error.
        """

        if not self.enabled:
            return

        if 'CONDITION_SCRIPT' not in self.config and 'CONDITION_DAT' not in self.config:
            return

        if 'CONDITION_SCRIPT' not in self.config or 'CONDITION_DAT' not in self.config:
            raise ValueError("Trigger condition of " + self.block + " needs both CONDITION_SCRIPT and "
                             "CONDITION_DAT parameters.")

        script = self.config['CONDITION_SCRIPT']
        dat_file = Path(self.config['CONDITION_DAT'])

        if not os.path.isfile(script):
            raise ValueError("Trigger condition script " + script + " does not exist.")
        if not os.path.isfile(dat_file):
            raise ValueError("Trigger condition file " + str(dat_file) + " does not exist.")

        if self.config.get('CONDITION_DAT_DATE_CHANGE', True):
            file_modifier.modify_start_dat_date(dat_file, file_modifier.date_to_mohid_date(current_initial_date),
                                                self.logger)
            file_modifier.modify_end_dat_date(dat_file, file_modifier.date_to_mohid_date(current_final_date),
                                              self.logger)

        self.logger.info("Checking trigger condition of " + self.block + ": " + script + " " + str(dat_file))
        result = subprocess.run([sys.executable, script, str(dat_file)], cwd=os.path.dirname(script),
                                capture_output=True, text=True)

        # The script output goes to its own log file instead of ART's main log
        log_folder = Path(self.yaml['ART']['LOG']['FOLDER_PATH']) / "checked_triggers" / self.block
        log_folder.mkdir(parents=True, exist_ok=True)
        log_file = log_folder / self._file_name(current_initial_date).replace(".dat", ".log")
        with open(log_file, 'w') as log:
            log.write(result.stdout)
            log.write(result.stderr)
        self.logger.info("Trigger condition output of " + self.block + " written to " + str(log_file))

        if result.returncode != 0:
            raise ValueError("Trigger condition script " + script + " failed with exit code " +
                             str(result.returncode) + ". See " + str(log_file) + ".")

        # The condition result is the last non-empty line printed by the script: True or False
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        answer = lines[-1] if lines else ""

        if answer not in ("True", "False"):
            raise ValueError("Trigger condition script " + script + " must print True or False as its last "
                             "line, got '" + answer + "'.")

        if answer == "False":
            raise TriggerConditionNotMet("Trigger condition of " + self.block + " is not met. Stopping execution.")

        self.logger.info("Trigger condition of " + self.block + " is met.")

    def write(self, current_initial_date, current_final_date, status):
        """ Writes the trigger file of the block with the given status ("Running" or "Finished"). """

        if not self.enabled or 'WRITE_TRIGGER' not in self.config:
            return

        if ('WRITE_TRIGGER' in self.config) and not self.config['WRITE_TRIGGER']:
            self.logger.info("Output trigger not set. WRITE_TRIGGER parameter is empty.")
            return

        log_path = self.yaml['ART']['LOG']['FOLDER_PATH']
        dest_folder = os.path.join(log_path, "triggers", self.block)

        if not os.path.isdir(dest_folder):
            os.makedirs(dest_folder)

        filepath = Path(dest_folder) / self._file_name(current_initial_date)
        system_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

        with open(filepath, 'w') as file:
            file.write('\n')
            file.write('FILE AUTOMATICALLY GENERATED TO BE USED AS TRIGGER')
            file.write('\n')
            file.write('DO NOT EDIT, CHANGE, MOVE, DELETE THIS FILE!')
            file.write('\n')
            file.write('\n')

            if status == "Running":
                file.write(self.block + ' is running for the following period:')
            elif status == "Finished":
                file.write(self.block + ' finished for the following period:')

            file.write('\n')
            file.write('START                         : ' + file_modifier.date_to_mohid_date(current_initial_date))
            file.write('\n')
            file.write('END                           : ' + file_modifier.date_to_mohid_date(current_final_date))
            file.write('\n')

            if status == "Running":
                file.write('STATUS                        : RUNNING')
            elif status == "Finished":
                file.write('STATUS                        : FINISHED')

            file.write('\n')
            file.write('SYSTEM TIME                   : ' + system_time)
