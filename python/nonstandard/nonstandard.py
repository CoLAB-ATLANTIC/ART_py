import datetime
import re

# import mohid.util.constants as static
import utils.constants as static

import common.pre_processing as pre_processing
import common.post_processing as post_processing
from common.model_base import ModelBase

class NonStandardModel(ModelBase):
    """ Model that ART does not run itself: only the pre-processing and post-processing blocks of the yaml
    are executed for every period.
    """

    def __init__(self, art, name):
        super().__init__(art, name)

    def execute(self):
        self.logger.info("Executing non-standard model for module: " + self.name)
        super().execute()

    def run_simulation(self, repeat_index: int):
        self.logger.info("Non-standard model " + self.name + " has no simulation step. Skipping RUN_SIMULATION.")
