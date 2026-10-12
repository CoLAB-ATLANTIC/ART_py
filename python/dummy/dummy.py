import datetime
import re
import mohid.util.constants as static
import common.pre_processing as pre_processing
import common.post_processing as post_processing


class DummyModel:
    def __init__(self, art, name):
        self.logger = art.logger
        self.yaml = art.yaml
        self.name = name
        self.global_initial_date = None
        self.number_of_runs = None
        self.current_initial_date = None
        self.current_final_date = None

    def execute(self):
        self.logger.info("Executing dummy model for module: " + self.name)
        artconfig_keys = self.yaml['ART'].keys()
        simulation_keys = self.yaml['SIMULATION'].keys()
        days_run = 0

        if 'OPERATIONAL_MODE' in simulation_keys and self.yaml['SIMULATION']['OPERATIONAL_MODE']:
            self.logger.info("Running Dummy model in Operational Mode")

            if 'AUTOMATIC_DATE' in simulation_keys and self.yaml['SIMULATION']['AUTOMATIC_DATE']:
                today = datetime.datetime.today()
            else:
                print(self.yaml['SIMULATION'])
                # No caso de se querer simular o esquema operational em modo hindcast
                # Ler aqui o ficheiro de control.dat (tem de estar no mesmo local que o art.yaml)
                with open("control.dat", "r") as file:
                    for line in file.readlines():
                        if re.search("^START.+:", line):
                            StartDate = line.split()
                today = datetime.datetime(int(StartDate[2]),int(StartDate[3]),int(StartDate[4]),int(StartDate[5]),0,0)

            # Time needs to start on hour 00:00:00 otherwise will start at the wrong time
            today = today.replace(minute=00, hour=00, second=00)
            self.global_initial_date = today + datetime.timedelta(days=self.yaml['SIMULATION']['REF_DAYS_TO_START'])
            self.number_of_runs = self.yaml['SIMULATION']['NUMBER_OF_RUNS']

            for i in range(1, self.number_of_runs + 1):
                self.current_initial_date = self.global_initial_date + datetime.timedelta(days=i - 1)
                self.current_final_date = self.current_initial_date + datetime.timedelta(
                    days=self.yaml['SIMULATION']['DAYS_PER_RUN'])

                self.logger.info("========================================")
                self.logger.info("STARTING FORECAST ( " + str(i) + " of " + str(self.number_of_runs) + " )")
                self.logger.info("========================================")

                self.run_processing(artconfig_keys, days_run)
        else:
            self.current_initial_date = datetime.datetime.strptime(self.yaml['SIMULATION']['START_DATE'],
                                                                   static.DATE_FORMAT).replace(minute=00, hour=00, second=00)
            self.current_final_date = self.current_initial_date + datetime.timedelta(
                days=self.yaml['SIMULATION']['DAYS_PER_RUN'])

            self.run_processing(artconfig_keys, days_run)

        self.logger.info("Dummy model " + self.name + " finished.")

    def run_processing(self, artconfig_keys, days_run):
        if 'PRE_PROCESSING' in artconfig_keys and self.yaml['ART']['PRE_PROCESSING']:
            self.logger.info("Executing Pre Processing")
            pre_processing.execute(self.yaml, self.logger, self.current_initial_date, self.current_final_date,days_run)

        if 'POST_PROCESSING' in artconfig_keys and self.yaml['ART']['POST_PROCESSING']:
            print("Executing Post Processing")
            self.logger.info("Executing Post Processing")
            post_processing.execute(self.yaml, self.logger, self.current_initial_date, self.current_final_date,days_run)
