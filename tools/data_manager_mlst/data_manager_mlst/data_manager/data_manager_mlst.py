#!/usr/bin/env python3
"""
Galaxy Data Manager for PubMLST.
Downloads all PubMLST databases, creates a combined BLAST database,
and writes a Galaxy-compatible data table JSON.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import datetime
from urllib.request import urlopen


class MLSTDataManager:
    def __init__(self, json_path: str):
        self.json_path = json_path
        self.extra_files_path = None
        self.output_dir = None
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.db_name = f"mlst_database_{self.timestamp}"

    # ----------------------------------------------------------------------
    # Galaxy JSON I/O
    # ----------------------------------------------------------------------

    def read_input_json(self):
        """Read Galaxy input JSON and create the output directory."""
        with open(self.json_path) as fh:
            params = json.load(fh)
        self.extra_files_path = params["output_data"][0]["extra_files_path"]
        os.makedirs(self.extra_files_path, exist_ok=True)
        self.output_dir = os.path.abspath(self.extra_files_path)

    def write_output_json(self):
        """Write the final Galaxy data manager JSON."""
        entry = {
            "data_tables": {
                "mlst": [
                    {
                        "value": self.db_name,
                        "name": self.db_name,
                        "path": "mlst-db"
                    }
                ]
            }
        }

        with open(self.json_path, "w") as fh:
            json.dump(entry, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())

    # ----------------------------------------------------------------------
    # Database steps
    # ----------------------------------------------------------------------

    def download_pubmlst_databases(self):
        """Download all PubMLST databases."""
        print("Downloading PubMLST databases...")
        try:
            subprocess.run(["mlst-download_pub_mlst", "-d", "pubmlst"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error downloading databases: {e}")
            sys.exit(1)

    def make_blast_database(self):
        """Build a BLAST database from the downloaded data."""
        cwd = os.getcwd()
        src_dir = os.path.join(cwd, "pubmlst")
        dst_dir = os.path.join(self.output_dir, "pubmlst")

        if os.path.exists(dst_dir):
            shutil.rmtree(dst_dir)
        shutil.move(src_dir, dst_dir)

        blast_dir = os.path.join(self.output_dir, "blast")
        os.makedirs(blast_dir, exist_ok=True)
        blast_file = os.path.join(blast_dir, "mlst.fa")

        print("Building combined FASTA for BLAST database...")
        with open(blast_file, "a") as outfile:
            for scheme in os.listdir(dst_dir):
                scheme_path = os.path.join(dst_dir, scheme)
                if os.path.isdir(scheme_path):
                    for f in os.listdir(scheme_path):
                        if f.endswith(".tfa"):
                            with open(os.path.join(scheme_path, f)) as infile:
                                for line in infile:
                                    if "not a locus" not in line:
                                        if line.startswith(">"):
                                            outfile.write(f">{scheme}.{line[1:]}")
                                        else:
                                            outfile.write(line)

        print("Running makeblastdb...")
        subprocess.run([
            "makeblastdb", "-hash_index",
            "-in", blast_file, "-dbtype", "nucl",
            "-title", "PubMLST", "-parse_seqids"
        ], check=True)

    def download_scheme_species_map(self):
        """Fetch the scheme_species_map.tab file from GitHub."""
        url = "https://raw.githubusercontent.com/tseemann/mlst/master/db/scheme_species_map.tab"
        dst_file = os.path.join(self.output_dir, "scheme_species_map.tab")
        print("Downloading scheme_species_map.tab...")
        try:
            with urlopen(url) as response, open(dst_file, "w") as out:
                out.write(response.read().decode("utf-8"))
            print("scheme_species_map.tab downloaded successfully")
        except Exception as e:
            print(f"Failed to retrieve scheme_species_map.tab: {e}")

    # ----------------------------------------------------------------------
    # Run
    # ----------------------------------------------------------------------

    def run(self):
        try:
            self.read_input_json()
            self.download_pubmlst_databases()
            self.make_blast_database()
            self.download_scheme_species_map()
        except Exception as e:
            print(f"MLST Data Manager failed: {e}")
        finally:
            self.write_output_json()


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Galaxy Data Manager for PubMLST")
    parser.add_argument("data_manager_json", help="Galaxy data manager JSON file")
    return parser.parse_args()


def main():
    args = parse_args()
    mgr = MLSTDataManager(args.data_manager_json)
    mgr.run()


if __name__ == "__main__":
    main()

