import datetime
import re
from abc import ABC, abstractmethod

import utils.constants as static
import common.pre_processing as pre_processing
import common.post_processing as post_processing


class ModelBase(ABC):
    """ Common run cycle of every model executed by ART (MOHID Water, MOHID Land, SWAN, WW3, non-standard...).

    It computes the simulation dates from the SIMULATION section of the yaml and, for every period, runs the
    pre-processing, the model itself and the post-processing, according to the ART section of the yaml.
    A new model only needs to implement run_simulation, which runs the model for the current period.
    """

    def __init__(self, art, name):
        self.logger = art.logger
        self.yaml = art.yaml
        self.name = name
        self.global_initial_date = None
        self.global_final_date = None
        self.number_of_runs = None
        self.current_initial_date = None
        self.current_final_date = None

    @abstractmethod
    def run_simulation(self, repeat_index: int):
        """ Runs the model between self.current_initial_date and self.current_final_date. """

    def execute(self):
        self.set_global_dates()

        if self.yaml['SIMULATION']['OPERATIONAL_MODE']:
            self.logger.info("Running " + self.name + " in Operational Mode")
            self.run_operational()
        else:
            self.logger.info("Running " + self.name + " in Normal Mode")
            self.run_hindcast()

        self.logger.info(self.name + " finished.")

    def set_global_dates(self):
        """ Sets the global dates and the number of runs from the SIMULATION section of the yaml. """

        if 'SIMULATION' not in self.yaml:
            raise ValueError("SIMULATION key not defined in yaml configuration file.")

        simulation = self.yaml['SIMULATION']
        if 'OPERATIONAL_MODE' not in simulation:
            raise ValueError("OPERATIONAL_MODE keyword must be defined in yaml file.")

        days_per_run = simulation['DAYS_PER_RUN']

        if simulation['OPERATIONAL_MODE']:
            today = self._operational_reference_date()
            self.number_of_runs = simulation['NUMBER_OF_RUNS']
            self.global_initial_date = today + datetime.timedelta(days=simulation['REF_DAYS_TO_START'])
            self.global_final_date = self.global_initial_date + datetime.timedelta(
                days=self.number_of_runs - 1 + days_per_run)
        else:
            try:
                self.global_initial_date = datetime.datetime.strptime(simulation['START_DATE'], static.DATE_FORMAT)
                self.global_final_date = datetime.datetime.strptime(simulation['END_DATE'], static.DATE_FORMAT)
            except KeyError:
                raise ValueError("START_DATE and END_DATE must be defined in yaml file when OPERATIONAL_MODE is off.")
            self.number_of_runs = (self.global_final_date - self.global_initial_date).days

        self.logger.info("Global Initial Date : " + self.global_initial_date.strftime(static.DATE_FORMAT))
        self.logger.info("Global Final Date : " + self.global_final_date.strftime(static.DATE_FORMAT))
        self.logger.info("Number of runs : " + str(self.number_of_runs))

    def _operational_reference_date(self):
        """ Today at 00:00:00, or the START date of control.dat when AUTOMATIC_DATE is off (operational scheme
        simulated in hindcast mode). control.dat has to be in the same folder as the art.yaml.
        """

        if self.yaml['SIMULATION'].get('AUTOMATIC_DATE'):
            today = datetime.datetime.today()
        else:
            start_date = None
            with open("control.dat", "r") as file:
                for line in file.readlines():
                    if re.search("^START.+:", line):
                        start_date = line.split()
            if start_date is None:
                raise ValueError("START not found in control.dat and AUTOMATIC_DATE is off.")
            today = datetime.datetime(int(start_date[2]), int(start_date[3]), int(start_date[4]),
                                      int(start_date[5]), 0, 0)

        # Time needs to start on hour 00:00:00 otherwise the models will start at the wrong time
        return today.replace(minute=00, hour=00, second=00)

    def run_operational(self):
        """ NUMBER_OF_RUNS forecasts of DAYS_PER_RUN days, each one starting one day after the previous. """

        repeat_index = 0
        for i in range(1, self.number_of_runs + 1):
            self.current_initial_date = self.global_initial_date + datetime.timedelta(days=i - 1)
            self.current_final_date = self.current_initial_date + datetime.timedelta(
                days=self.yaml['SIMULATION']['DAYS_PER_RUN'])

            self._log_period_header("STARTING FORECAST ( " + str(i) + " of " + str(self.number_of_runs) + " )")
            self.run_period(repeat_index)

    def run_hindcast(self):
        """ Consecutive periods of DAYS_PER_RUN days (or one month with MONTH_MODE) from START_DATE to END_DATE.
        With RUN_TWICE every period is executed twice before moving to the next one.
        """

        global_final_date = self.global_final_date.replace(minute=00, hour=00, second=00)
        self.current_initial_date = self.global_initial_date.replace(minute=00, hour=00, second=00)
        self.current_final_date = self._period_end_date(self.current_initial_date)

        if self.current_final_date > global_final_date:
            self.logger.error("Time Date range is not big enough for a run.")
            return

        repeat_index = 0
        while self.current_final_date <= global_final_date:
            self._log_period_header("STARTING HINDCAST (" + self.current_initial_date.strftime("%Y-%m-%d") + " to " +
                                   self.current_final_date.strftime("%Y-%m-%d") + ")")
            self.run_period(repeat_index)

            if self.yaml['ART'].get('RUN_TWICE'):
                # Only run next period after repeating the current one. Useful for up-scaling
                repeat_index += 1
                if repeat_index == 1:
                    continue
                repeat_index = 0

            self.current_initial_date = self.current_final_date
            self.current_final_date = self._period_end_date(self.current_initial_date)

    def _period_end_date(self, initial_date):
        if self.yaml['SIMULATION'].get('MONTH_MODE'):
            # First day of the next month
            if initial_date.month == 12:
                return initial_date.replace(day=1, month=1, year=initial_date.year + 1, minute=00, hour=00, second=00)
            return initial_date.replace(day=1, month=initial_date.month + 1, minute=00, hour=00, second=00)
        return initial_date + datetime.timedelta(days=self.yaml['SIMULATION']['DAYS_PER_RUN'])

    def run_period(self, repeat_index: int):
        """ Pre-processing, model and post-processing of the current period, as enabled in the ART section. """

        artconfig = self.yaml['ART']

        if artconfig.get('PRE_PROCESSING'):
            self.logger.info("Executing Pre Processing")
            pre_processing.execute(self.yaml, self.logger, self.current_initial_date, self.current_final_date,
                                   repeat_index)

        if artconfig.get('RUN_SIMULATION'):
            self.run_simulation(repeat_index)

        if artconfig.get('POST_PROCESSING'):
            self.logger.info("Executing Post Processing")
            post_processing.execute(self.yaml, self.logger, self.current_initial_date, self.current_final_date,
                                    repeat_index)

    def _log_period_header(self, title):
        self.logger.info("========================================")
        self.logger.info(title)
        self.logger.info("========================================")
