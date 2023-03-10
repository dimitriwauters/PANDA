import os
import subprocess
import json
import sys
import time
from utility import write_debug_file, write_output_file

MAX_TRIES = 3

entropy_activated = True
memcheck_activated = False


def print_info(text):
    if not is_silent:
        print(text, flush=True)


if __name__ == "__main__":
    is_silent = os.getenv("panda_silent", default=False) == "True"
    is_debug = os.getenv("panda_debug", default=False) == "True"
    force_executable = os.getenv("panda_executable", default=None)
    if force_executable == "None":
        force_executable = None

    if is_debug:
        print_info("DEBUGGING ACTIVATED")
    if force_executable is not None:
        print_info(f"MALWARE ANALYSED: {force_executable}")

    print_info("++ Launching")
    result = {True: [], False: []}
    if force_executable is None:
        files_to_analyse = os.listdir("/payload")
    else:
        files_to_analyse = [force_executable]
    for malware_sample in files_to_analyse:
        if ".exe" in malware_sample:
            is_packed = False
            panda_output = None
            print_info(f"  -- Processing file '{malware_sample}'")
            for i in range(MAX_TRIES):
                panda_run_output, panda_replay_output = None, None
                print_info("    -- Creating ISO")
                subprocess.run(["genisoimage", "-max-iso9660-filenames", "-RJ", "-o", "payload.iso", f"/payload/{malware_sample}"], capture_output=True)
                try:
                    print_info("    -- Running PANDA")
                    panda_run_output = subprocess.run(["python3", "/addon/run_panda.py", malware_sample], capture_output=True)
                    time.sleep(2)
                    print_info("    -- Analysing PANDA output (might take a while)")
                    panda_replay_output = subprocess.run(["python3", "/addon/read_replay.py"], capture_output=True)
                    if is_debug:
                        write_debug_file(malware_sample, "run_panda", panda_run_output.stdout.decode())
                        write_debug_file(malware_sample, "read_replay", panda_replay_output.stdout.decode())
                except subprocess.CalledProcessError as e:
                    print_info("    !! An error occurred when trying to execute PANDA:")
                    print_info(e.stderr.decode())
                    sys.exit(e.returncode)

                with open("replay_result.txt", "r") as file:
                    panda_output = file.read()
                if panda_output != "ERROR":
                    break
                else:
                    print_info(f"  !! An error occurred when recovering the output of PANDA, retrying... ({i+1} of {MAX_TRIES})\n")

            if panda_output:
                panda_output_dict = json.loads(panda_output.replace("'", "\""))
                if memcheck_activated:
                    memory_write_list = panda_output_dict["memory_write_exe_list"]
                    if len(memory_write_list) > 0:
                        # TODO: Check if consecutive
                        """count = 0
                        for elem in memory_write_list:
                            addr = elem[1] % 134  # Modulo x86, the length of an instruction
                            print(addr)"""
                        is_packed = True
                    write_output_file(malware_sample, is_packed, "memcheck", memory_write_list)
                    result[is_packed].append(malware_sample)
                if entropy_activated:
                    entropy = panda_output_dict["entropy"]
                    entropy_initial_oep = panda_output_dict["entropy_initial_oep"]
                    entropy_unpacked_oep = panda_output_dict["entropy_unpacked_oep"]
                    entropy_val = {}
                    for instr_nbr in entropy:
                        current_dict = entropy[instr_nbr]
                        for header_name in current_dict:
                            if header_name not in entropy_val:
                                entropy_val[header_name] = ([], [])
                            entropy_val[header_name][0].append(int(instr_nbr))
                            entropy_val[header_name][1].append(current_dict[header_name])
                    for header_name in entropy_val:
                        has_initial_eop, has_unpacked_eop = False, False
                        if header_name == entropy_initial_oep[0]:
                            has_initial_eop = True
                        if header_name == entropy_unpacked_oep[0]:
                            has_unpacked_eop = True
                        write_output_file(malware_sample, is_packed, f"{header_name}_entropy", f"{entropy_val[header_name][0]}\n{entropy_val[header_name][1]}\n{has_initial_eop}-{entropy_initial_oep[1]}\n{has_unpacked_eop}-{entropy_unpacked_oep[1]}")
                result[is_packed].append(malware_sample)
                print_info("      -- The result of the analysis is: {}\n".format("PACKED" if is_packed else "NOT-PACKED"))
    print_info("++ Finished")

    # Show results
    total_analyzed = len(result[True])+len(result[False])
    percent_packed = len(result[True])/total_analyzed
    percent_not_packed = len(result[False])/total_analyzed
    print_info("*** % packed: {}\n*** % non-packed: {}".format(percent_packed, percent_not_packed))
    print_info("*** Packed list: {}".format(result[True]))
    print_info("*** Non-Packed list: {}".format(result[False]))

