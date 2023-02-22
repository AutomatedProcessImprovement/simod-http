import logging
import os
from pathlib import Path
from typing import Optional


def convert_xes_to_csv_if_needed(log_path: Path, output_path: Optional[Path] = None) -> Path:
    _, ext = os.path.splitext(log_path)
    if ext != '.csv':
        if output_path:
            log_path_csv = output_path
        else:
            log_path_csv = log_path.with_suffix('.csv')
        convert_xes_to_csv(log_path, log_path_csv)
        return log_path_csv
    else:
        return log_path


def convert_xes_to_csv(xes_path: Path, csv_path: Path):
    args = ['poetry', 'run', 'pm4py_wrapper', '-i', str(xes_path), '-o', str(csv_path.parent), 'xes-to-csv']
    logging.info(f'Executing shell command: {args}')
    os.system(' '.join(args))
