import datetime
import os
import re
import subprocess
from abc import ABC, abstractmethod

from pathlib import Path

import utils.constants as static
import common.pre_processing as pre_processing
import common.post_processing as post_processing
from common.trigger import Trigger


class ModelBase(ABC):
    """Common run cycle of every model executed by ART (MOHID Water, MOHID Land, SWAN, WW3, non-standard...).

    It computes the simulation dates from the SIMULATION section of the yaml and, for every period, runs the
    pre-processing, the model itself and the post-processing, according to the ART section of the yaml.
    A new model only needs to implement `run_simulation`, which runs the model for the current period.

    Parameters
    ----------
    art : ART
        Running ART instance, from which the logger and the parsed yaml are taken.
    name : str
        Name of the model, used in the logs and in the trigger files.

    Attributes
    ----------
    logger : logging.Logger
        Logger shared with ART.
    yaml : dict
        Whole parsed yaml configuration.
    name : str
        Name of the model.
    config : dict
        yaml section of the model (e.g. ``yaml['MOHID_WATER']``), set by each subclass.
    global_initial_date, global_final_date : datetime.datetime
        Limits of the whole simulation, set by `_set_global_dates`.
    number_of_runs : int
        Number of periods of the simulation, set by `_set_global_dates`.
    current_initial_date, current_final_date : datetime.datetime
        Limits of the period being run.
    trigger : Trigger
        Trigger of the model run, built in `execute`.
    """

    def __init__(self, art, name):
        self.logger = art.logger
        self.yaml = art.yaml
        self.name = name
        # yaml section of the model (e.g. self.yaml['MOHID_WATER']), set by each subclass
        self.config = {}
        self.global_initial_date = None
        self.global_final_date = None
        self.number_of_runs = None
        self.current_initial_date = None
        self.current_final_date = None
        self.trigger = None

    # ------------------------------------------------------------------
    # Contract for subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    def run_simulation(self, repeat_index: int):
        """Run the model between `current_initial_date` and `current_final_date`.

        Parameters
        ----------
        repeat_index : int
            0 on the first execution of the period, 1 on its repetition when RUN_TWICE is on.
        """

    def _trigger_folder(self) -> Path:
        """Folder where the trigger files of the model run are written.

        Subclasses can override it to use a different folder.

        Returns
        -------
        Path
            ``<ART.LOG.FOLDER_PATH>/triggers``.
        """
        return Path(self.yaml['ART']['LOG']['FOLDER_PATH']) / "triggers"

    # ------------------------------------------------------------------
    # Run cycle
    # ------------------------------------------------------------------

    def execute(self):
        """Run the whole simulation of the model.

        Sets the global dates, builds the trigger and runs every period in operational or hindcast mode,
        depending on SIMULATION.OPERATIONAL_MODE.
        """
        self._set_global_dates()
        # Built here and not in __init__ because subclasses set self.config after calling super().__init__
        self.trigger = Trigger.for_model(self.yaml, self.logger, self.name, self._trigger_folder())

        if self.yaml['SIMULATION']['OPERATIONAL_MODE']:
            self.logger.info("Running " + self.name + " in Operational Mode")
            self._run_operational()
        else:
            self.logger.info("Running " + self.name + " in Normal Mode")
            self._run_hindcast()

        self.logger.info(self.name + " finished.")

    def _set_global_dates(self):
        """Set the global dates and the number of runs from the SIMULATION section of the yaml.

        In operational mode the simulation starts REF_DAYS_TO_START days after the reference date and lasts
        NUMBER_OF_RUNS runs. Otherwise it goes from START_DATE to END_DATE.

        Raises
        ------
        ValueError
            If SIMULATION or OPERATIONAL_MODE are missing, or if START_DATE and END_DATE are missing when
            OPERATIONAL_MODE is off.
        """

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
        """Reference date of the operational mode.

        It is today when AUTOMATIC_DATE is on, or the START date of control.dat otherwise (operational scheme
        simulated in hindcast mode). control.dat has to be in the same folder as the art.yaml.

        Returns
        -------
        datetime.datetime
            Reference date at 00:00:00.

        Raises
        ------
        ValueError
            If AUTOMATIC_DATE is off and control.dat has no START line.
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

    def _run_operational(self):
        """Run NUMBER_OF_RUNS forecasts of DAYS_PER_RUN days, each one starting one day after the previous."""

        repeat_index = 0
        for i in range(1, self.number_of_runs + 1):
            self.current_initial_date = self.global_initial_date + datetime.timedelta(days=i - 1)
            self.current_final_date = self.current_initial_date + datetime.timedelta(
                days=self.yaml['SIMULATION']['DAYS_PER_RUN'])

            self._log_period_header("STARTING FORECAST ( " + str(i) + " of " + str(self.number_of_runs) + " )")
            self._run_period(repeat_index)

    def _run_hindcast(self):
        """Run consecutive periods from START_DATE to END_DATE.

        Every period lasts DAYS_PER_RUN days, or one month with MONTH_MODE. With RUN_TWICE every period is executed
        twice before moving to the next one. Nothing is run if the date range is shorter than one period.
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
            self._run_period(repeat_index)

            if self.yaml['ART'].get('RUN_TWICE'):
                # Only run next period after repeating the current one. Useful for up-scaling
                repeat_index += 1
                if repeat_index == 1:
                    continue
                repeat_index = 0

            self.current_initial_date = self.current_final_date
            self.current_final_date = self._period_end_date(self.current_initial_date)

    def _period_end_date(self, initial_date):
        """End date of the hindcast period that starts at `initial_date`.

        Parameters
        ----------
        initial_date : datetime.datetime
            Start of the period.

        Returns
        -------
        datetime.datetime
            First day of the next month at 00:00:00 with MONTH_MODE, `initial_date` plus DAYS_PER_RUN days
            otherwise.
        """
        if self.yaml['SIMULATION'].get('MONTH_MODE'):
            # First day of the next month
            if initial_date.month == 12:
                return initial_date.replace(day=1, month=1, year=initial_date.year + 1, minute=00, hour=00, second=00)
            return initial_date.replace(day=1, month=initial_date.month + 1, minute=00, hour=00, second=00)
        return initial_date + datetime.timedelta(days=self.yaml['SIMULATION']['DAYS_PER_RUN'])

    def _run_period(self, repeat_index: int):
        """Run the pre-processing, the model and the post-processing of the current period.

        Each step only runs when enabled in the ART section (PRE_PROCESSING, RUN_SIMULATION, POST_PROCESSING).
        The model run is checked against the trigger first and writes its status to it.

        Parameters
        ----------
        repeat_index : int
            0 on the first execution of the period, 1 on its repetition when RUN_TWICE is on.
        """

        artconfig = self.yaml['ART']

        if artconfig.get('PRE_PROCESSING'):
            self.logger.info("Executing Pre Processing")
            pre_processing.execute(self.yaml, self.logger, self.current_initial_date, self.current_final_date,
                                   repeat_index)

        if artconfig.get('RUN_SIMULATION'):
            self.trigger.check(repeat_index, self.current_initial_date)
            self.trigger.check_condition(self.current_initial_date, self.current_final_date)
            self.trigger.write(self.current_initial_date, self.current_final_date, status="Running")
            self.run_simulation(repeat_index)
            self.trigger.write(self.current_initial_date, self.current_final_date, status="Finished")

        if artconfig.get('POST_PROCESSING'):
            self.logger.info("Executing Post Processing")
            post_processing.execute(self.yaml, self.logger, self.current_initial_date, self.current_final_date,
                                    repeat_index)

    def _log_period_header(self, title):
        """Log `title` between two separator lines.

        Parameters
        ----------
        title : str
            Header text of the period.
        """
        self.logger.info("========================================")
        self.logger.info(title)
        self.logger.info("========================================")

    # ------------------------------------------------------------------
    # Toolkit for subclasses
    # ------------------------------------------------------------------

    @property
    def mpi_enabled(self) -> bool:
        """bool: Whether MPI.ENABLE is on in the model section."""
        return bool(self.config.get('MPI', {}).get('ENABLE', False))

    @property
    def openmp_enabled(self) -> bool:
        """bool: Whether OPENMP.ENABLE is on in the model section."""
        return bool(self.config.get('OPENMP', {}).get('ENABLE', False))

    def run_executable(self, exe_path, cwd, log_file):
        """Run the model executable (serial, OpenMP or MPI), writing its stdout to `log_file`.

        Parameters
        ----------
        exe_path : str or Path
            Path of the model executable.
        cwd : str or Path
            Working directory of the run.
        log_file : str or Path
            File where the stdout of the run is written. It is overwritten if it exists.
        """
        mode = "MPI" if self.mpi_enabled else "OpenMP" if self.openmp_enabled else "serial"
        self.logger.info(f"Starting {self.name} run ({mode})")
        with open(log_file, "w+") as output_file:
            subprocess.run(self._run_command(exe_path), cwd=cwd, stdout=output_file, env=self._run_env())

    def _run_command(self, exe_path) -> list:
        """Command that runs the executable.

        With MPI it goes through the launcher in MPI.EXE_PATH (mpiexec by default, or srun). With OpenMP it goes
        through srun when OPENMP.EXE_PATH is srun. Otherwise the executable runs alone.

        Parameters
        ----------
        exe_path : str or Path
            Path of the model executable.

        Returns
        -------
        list of str
            Command and arguments, ready for `subprocess.run`.
        """
        if self.mpi_enabled:
            mpi_config = self.config['MPI']
            if 'EXE_PATH' in mpi_config:
                launcher = str(mpi_config['EXE_PATH'])
            else:
                launcher = "mpiexec"
                self.logger.info("Executable information for MPI missing. Defaulting to mpiexec.")
            processors_flag = "-n" if launcher == "srun" else "-np"
            return [launcher, processors_flag, str(mpi_config['TOTAL_PROCESSORS']), str(exe_path)]

        if self.openmp_enabled and self.config['OPENMP'].get('EXE_PATH') == "srun":
            return ["srun", "-T", str(self.config['OPENMP']['TOTAL_PROCESSORS']), str(exe_path)]

        return [str(exe_path)]

    def _run_env(self):
        """Environment of the model run.

        Returns
        -------
        dict or None
            The current environment with OMP_NUM_THREADS set to OPENMP.TOTAL_PROCESSORS when OpenMP is on and
            TOTAL_PROCESSORS is given, None (inherit the current environment) otherwise.
        """
        if self.openmp_enabled and 'TOTAL_PROCESSORS' in self.config['OPENMP']:
            return {**os.environ, 'OMP_NUM_THREADS': str(self.config['OPENMP']['TOTAL_PROCESSORS'])}
        return None
