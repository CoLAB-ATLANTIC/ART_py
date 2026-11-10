import datetime
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mohid.mohid_water import MohidWater


class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {
            'MAIN_PATH': str(self.root),
            'TREE_PATH': str(self.root) + '/',
            'EXE_PATH': str(self.root / 'MohidWater.exe'),
            'MPI': {'ENABLE': True},
            'MODELS': {name: {'NAME': name, 'PATH': name + '/'} for name in ('outer', 'inner')},
        }
        self.model = MohidWater(SimpleNamespace(logger=Mock(), yaml={'MOHID_WATER': self.config}))
        self.model.current_initial_date = datetime.datetime(2026, 1, 1)

    def write_list(self, model, rank, contents):
        path = self.root / model / 'res' / f'MPI_{rank}_DecomposedFiles.dat'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def run_ddc(self):
        with patch('mohid.mohid_water.subprocess.run', return_value=SimpleNamespace(returncode=0)) as run:
            with patch.object(self.model, '_verify_log') as verify:
                self.model.run_ddc()
            verify.assert_called_once()
        return run.call_args

    def test_count_deduplicates_ranks_but_keeps_models_separate(self):
        self.write_list('outer', 1, 'MPI_1_Hydro.hdf5\nMPI_1_Hydro.fin\n\n')
        self.write_list('outer', 2, 'MPI_2_Hydro.hdf5\nMPI_2_Hydro.fin\n')
        self.write_list('inner', 1, 'MPI_1_Hydro.hdf5\n')
        self.assertEqual(self.model.count_consolidation_files(), 3)

    def test_serial_consolidation_remains_default(self):
        self.config['MPI']['MOHID_CONSOLIDATION_EXE'] = 'custom_ddc'
        call = self.run_ddc()
        self.assertEqual(call.args[0], [str(self.root / 'custom_ddc'), self.config['EXE_PATH']])
        self.assertEqual(call.kwargs['stderr'], -2)  # subprocess.STDOUT

    def test_mpi_caps_processors_and_handles_absolute_srun(self):
        self.write_list('outer', 1, 'MPI_1_a.fin\nMPI_1_b.fin\nMPI_1_c.fin\n')
        self.config['MPI'].update(MOHID_CONSOLIDATION_MPI=True,
                                  MOHID_CONSOLIDATION_MAX_PROCESSORS=2, EXE_PATH='/usr/bin/srun')
        call = self.run_ddc()
        self.assertEqual(call.args[0], ['/usr/bin/srun', '-n', '2',
                                       str(self.root / 'DomainDecompositionConsolidation.exe')])

    def test_mpi_uses_available_processors_by_default(self):
        self.config['MPI']['MOHID_CONSOLIDATION_MPI'] = True
        self.write_list('outer', 1, 'MPI_1_a.fin\nMPI_1_b.fin\n')
        with patch.object(self.model, 'available_processors', return_value=1):
            call = self.run_ddc()
        self.assertEqual(call.args[0][:3], ['mpiexec', '-np', '1'])

    def test_empty_lists_fall_back_to_one_processor(self):
        self.config['MPI'].update(MOHID_CONSOLIDATION_MPI=True, MOHID_CONSOLIDATION_MAX_PROCESSORS=4)
        self.assertEqual(self.run_ddc().args[0][2], '1')

    def test_invalid_processor_cap_is_rejected_before_launch(self):
        for cap in (0, -1):
            with self.subTest(cap=cap):
                self.config['MPI'].update(MOHID_CONSOLIDATION_MPI=True,
                                          MOHID_CONSOLIDATION_MAX_PROCESSORS=cap)
                with patch('mohid.mohid_water.subprocess.run') as run:
                    with self.assertRaisesRegex(ValueError, 'must be at least 1'):
                        self.model.run_ddc()
                    run.assert_not_called()

    def test_available_processors(self):
        with patch.dict(os.environ, {'SLURM_NTASKS': '3'}):
            self.assertEqual(self.model.available_processors(), 3)
        with patch.dict(os.environ, {'SLURM_NTASKS': ''}):
            with patch('os.sched_getaffinity', return_value={0, 1}, create=True):
                self.assertEqual(self.model.available_processors(), 2)
            with patch('os.sched_getaffinity', create=True):
                del os.sched_getaffinity
                with patch('os.cpu_count', return_value=None):
                    self.assertEqual(self.model.available_processors(), 1)

    def test_bypass_filters_all_models_before_one_consolidation(self):
        paths = [self.write_list(name, 1, 'MPI_1_a.fin\nMPI_1_b.fin5\nMPI_1_a.hdf5\n')
                 for name in self.config['MODELS']]

        def consolidate():
            for path in paths:
                self.assertEqual(path.read_text(), 'MPI_1_a.fin\nMPI_1_b.fin5\n')
            self.assertEqual(self.model.count_consolidation_files(), 4)

        with patch.object(self.model, 'run_ddc', side_effect=consolidate) as run:
            self.model.backup_decomposedfiles()
            run.assert_called_once()
        for path in paths:
            self.assertEqual(path.read_text(), 'MPI_1_a.hdf5\n')
            self.assertEqual(Path(str(path) + 'x').read_text(),
                             'MPI_1_a.fin\nMPI_1_b.fin5\nMPI_1_a.hdf5\n')

    def test_failed_bypass_restores_original_lists(self):
        paths = [self.write_list(name, 1, 'MPI_1_a.fin\nMPI_1_a.hdf5\n')
                 for name in self.config['MODELS']]
        with patch.object(self.model, 'run_ddc', side_effect=ValueError('DDC failed')):
            with self.assertRaisesRegex(ValueError, 'DDC failed'):
                self.model.backup_decomposedfiles()
        for path in paths:
            self.assertEqual(path.read_text(), 'MPI_1_a.fin\nMPI_1_a.hdf5\n')

    def test_nonzero_ddc_exit_is_rejected(self):
        with patch('mohid.mohid_water.subprocess.run', return_value=SimpleNamespace(returncode=2)):
            with self.assertRaisesRegex(ValueError, 'exit code 2'):
                self.model.run_ddc()


if __name__ == '__main__':
    unittest.main()
