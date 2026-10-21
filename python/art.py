from logging import error
import common.yaml.yaml_lib as yaml_lib
import mohid.mohid_water as mohid_water
import swan.swan as swan
import ww3.ww3 as ww3
import nonstandard.nonstandard as nonstandard
import common.MailClient as mail
import datetime
import os.path
import sys

from pathlib import Path
import common.logger as logger

def open_and_validate_yaml(path):
    yaml_file = yaml_lib.open_yaml_file(path)
    return yaml_file


def get_log_file(yaml):
    now = datetime.datetime.now()
    now_str = now.strftime("%y-%m-%d_%H%M%S")
    file_path = f"ART_{now_str}.log"
    folder_path = Path(yaml['ART']['PROJECT_PATH'] + "/logs")

    if not folder_path.is_dir():
        os.makedirs(folder_path)

    return folder_path / file_path


# Modules ART knows how to run, in execution order: yaml key -> (log label, function that runs it from ART)
KNOWN_MODULES = {
    'MOHID_WATER': ("MOHID Water", lambda art: mohid_water.MohidWater(art).execute()),
    'MOHID_LAND': ("MOHID Land", None),
    'SWAN': ("Swan", swan.execute),
    'WW3': ("Wavewatch III", ww3.execute),
}

class ART:
    def __init__(self, yaml):
        self.yaml = yaml
        self.log_path = get_log_file(yaml)
        self.logger = logger.ArtLogger("ART", self.log_path)
        self.mail = self.initialize_mail(yaml)
        if self.mail is not None:
            self.mail.attachment = self.log_path

    def initialize_mail(self, yaml):
        if 'EMAIL_NOTIFICATION' in yaml['ART'].keys() and yaml['ART']['EMAIL_NOTIFICATION']['ENABLE']:
            self.logger.info("Email Notification enabled.")
            self.logger.info("Sending notifications to: " + str(yaml['ART']['EMAIL_NOTIFICATION']['RECEIVERS'][0]))
            return mail.MailClient(yaml['ART']['EMAIL_NOTIFICATION']['USER'], yaml['ART']['EMAIL_NOTIFICATION']['PASSWORD'], yaml['ART']['EMAIL_NOTIFICATION']['RECEIVERS'])

    def execute_module(self):
        modules = self.yaml['ART'].get('MODULE')
        if not modules:
            self.logger.info("Module Keyword not found. Skipping Simulation...")
            return

        try:
            for module_name, (label, run) in KNOWN_MODULES.items():
                if modules.get(module_name):
                    self.logger.info(f"Starting {label} module")
                    run(self)
            # Any other enabled module only runs its pre-processing and post-processing
            for module_name, enabled in modules.items():
                if enabled and module_name not in KNOWN_MODULES:
                    self.logger.info("Starting non-standard module for " + module_name)
                    nonstandard.NonStandardModel(self, module_name).execute()
        except ValueError as e:
            self.logger.error(str(e))
            self.error_routine(e)

    def error_routine(self, error):
        if(self.mail != None):
            self.mail.send_not_ok_email(error.__str__())
        self.logger.info("ART IS EXITING WITH AN ERROR.")
        sys.exit(0)

    def exit_routine(self):
        self.logger.info("------------- ART RUN FINISHED -------------")


def validate_path(path):
    return os.path.exists(path)

def main():
    yaml = open_and_validate_yaml(sys.argv[1])
    art = ART(yaml)
    art.execute_module()
    art.exit_routine()

if __name__ == "__main__":
    main()
