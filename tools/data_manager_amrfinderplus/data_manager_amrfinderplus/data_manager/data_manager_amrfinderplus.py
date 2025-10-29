#!/usr/bin/env python3
"""
Galaxy Data Manager for NCBI AMRFinderPlus database.
Downloads and indexes the AMRFinderPlus database using amrfinder_update.
Writes a Galaxy-compatible data table JSON.
"""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


class AmrFinderPlusDataManager:
    def __init__(self, json_path: str, db_name="amrfinderplus-db"):
        self.json_path = Path(json_path)
        self.db_name = db_name
        self.output_dir = None
        self.extra_files_path = None
        self.version = None
        self.dbformat = None

    # --- Galaxy I/O ---------------------------------------------------------

    def read_input_json(self):
        """Read the input Galaxy data manager JSON."""
        with open(self.json_path) as fh:
            params = json.load(fh)

        # Galaxy passes where we can write files (extra_files_path)
        self.extra_files_path = Path(params["output_data"][0]["extra_files_path"])
        self.extra_files_path.mkdir(parents=True, exist_ok=True)
        self.output_dir = self.extra_files_path / "tmp_download"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_output_json(self):
        """Write Galaxy data table JSON entry."""
        entry = {
            "data_tables": {
                "amrfinderplus_versioned_database": [
                    {
                        "value": f"amrfinderplus_{self.version}_{self.dbformat}",
                        "name": f"{self.version} ({self.dbformat})",
                        "db_version": self.dbformat,
                        "path": self.db_name,
                    }
                ]
            }
        }

        # Overwrite Galaxy's job JSON atomically and flush it
        with open(self.json_path, "w") as fh:
            json.dump(entry, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())

    # --- Database logic -----------------------------------------------------

    def run_amrfinder_update(self):
        """Run amrfinder_update to download the database."""
        print(f"Running amrfinder_update -d {self.output_dir}")
        subprocess.run(["amrfinder_update", "-d", str(self.output_dir)], check=True)

    def read_versions(self):
        """Read version.txt and database_format_version.txt."""
        latest_dir = self.output_dir / "latest"
        with open(latest_dir / "version.txt") as f:
            self.version = f.readline().strip()
        with open(latest_dir / "database_format_version.txt") as f:
            self.dbformat = f.readline().strip()

    def copy_database(self):
        """Copy the downloaded database to a permanent location."""
        latest_dir = self.output_dir / "latest"
        final_dir = self.extra_files_path / self.db_name
        shutil.copytree(latest_dir, final_dir, dirs_exist_ok=True)

    def cleanup(self):
        """Remove temporary download folder."""
        shutil.rmtree(self.output_dir, ignore_errors=True)

    # --- Main run -----------------------------------------------------------

    def run(self):
        try:
            self.read_input_json()
            self.run_amrfinder_update()
            self.read_versions()
            self.copy_database()
        except Exception as e:
            print(f"AMRFinderPlus Data Manager failed: {e}")
            # still record placeholder entry
            self.version = "unknown"
            self.dbformat = "unknown"
        finally:
            self.cleanup()
            self.write_output_json()


# --- CLI entrypoint --------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Galaxy Data Manager for AMRFinderPlus database")
    parser.add_argument("data_manager_json", help="Galaxy data manager input/output JSON file")
    return parser.parse_args()


def main():
    args = parse_args()
    mgr = AmrFinderPlusDataManager(args.data_manager_json)
    mgr.run()


if __name__ == "__main__":
    main()

