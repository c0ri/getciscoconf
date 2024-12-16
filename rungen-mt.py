import paramiko
import time
import re
import argparse
from getpass import getpass
from datetime import datetime
import os
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


# -- Define a global verbose flag
verbose = False

def ensure_directory_exists(directory):
    # -- Ensures the directory exists, creates it if not.
    curr_dir = os.getcwd()
    check_dir = curr_dir + "/" + directory
    if not os.path.exists(check_dir):
        os.makedirs(check_dir)

def is_enabled(shell, timeout):
    start_time = time.time()
    buffer = ''
    print(f"Checking if we are enabled: ", end='')
    while time.time() - start_time < timeout:
        if shell.recv_ready():
            buffer += shell.recv(65535).decode('utf-8')
            if re.search(r'>', buffer):
                print("NO.")
                return False
            elif re.search(r'#', buffer):
                print("YES.")
                return True
            print("Unable to determine prompt.")
            return False
        
        time.sleep(1)
    return False

def verbose_print(message):
    # -- Prints the message only if verbosity is enabled.
    if verbose:
        print(f"[{datetime.now().strftime('%Y%m%d%H%M%S')}] {message}")

def wait_for_prompt(shell, prompt, timeout):
    start_time = time.time()
    buffer = ''
    while time.time() - start_time < timeout:
        if shell.recv_ready():
            buffer += shell.recv(65535).decode('utf-8')
            if re.search(prompt, buffer):
                return True
        time.sleep(1)
    return False

def wait_for_command_output(shell, command, prompt, hostname, timeout, session_log_file):
    """
    Waits for the output of a given command and logs it to the appropriate file.
    Handles multi-threading with care to avoid timing issues.
    """
    start_time = time.time()  # -- Unique to each thread
    command_output = ''
    verbose_print(f"Running command: {command} (Thread: {threading.current_thread().name})")

    while time.time() - start_time < timeout:
        if shell.recv_ready():
            command_output += shell.recv(65535).decode('utf-8')
            if re.search(prompt, command_output):
                break
        time.sleep(1)

    # -- Warn only if the prompt isn't found after timeout
    if not re.search(prompt, command_output):
        verbose_print(f"Warning (Thread {threading.current_thread().name}): Command '{command}' output did not end with expected prompt '{prompt}'.")
    else:
        verbose_print(f"Command '{command}' completed successfully with expected prompt (Thread {threading.current_thread().name}).")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    if "show run" in command.lower():
        sanitized_command = "config"
        config_filename = f"configs/{hostname}-{timestamp}-{sanitized_command}.log"
        verbose_print(f"Saving 'show run' output to {config_filename}")
        with threading.Lock():  # -- Ensure no race conditions when writing to files
            with open(config_filename, "w") as file:
                file.write(command_output)
    else:
        verbose_print(f"Appending command output to session log {session_log_file}")
        with threading.Lock():  # -- Protect shared resources
            with open(session_log_file, "a") as file:
                file.write(f"\n--- Output for command: {command} ---\n")
                file.write(command_output)

    return command_output


def connect_to_device(hostname, username, password, enable_password, commands, timeout):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    verbose_print(f"---------------------------------------------------")
    verbose_print(f"Working on {hostname}")
    verbose_print(f"---------------------------------------------------")
    try:
        verbose_print(f"Connecting to {hostname}")
        ssh.connect(hostname, username=username, password=password, look_for_keys=False, allow_agent=False)

        verbose_print(f"Opening shell on {hostname}: ")
        shell = ssh.invoke_shell()
        time.sleep(2)
        verbose_print(f"Connected!")

        # -- Prepare session log file
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        session_log_file = f"logs/{hostname}-session-{timestamp}.log"

        # -- Check if in enabled mode; if not, enter it
        if not is_enabled(shell, timeout):
            verbose_print(f"Entering enable mode...")
            wait_for_prompt(shell, r'>', timeout)
            shell.send("enable\n")
            time.sleep(2)
            shell.send(f"{enable_password}\n")
            time.sleep(2)

        verbose_print(f"Setting terminal length to 0")
        shell.send("terminal length 0\n")
        time.sleep(1)
        wait_for_prompt(shell, r'#', timeout)

        # -- Process each command in the list
        for command in commands:
            # -- Skip blank lines or lines with only "!"
            if not command.strip() or command.strip() == "!":
                verbose_print(f"Skipping invalid command: '{command}'")
                continue
            
            # -- Send the command and process output
            shell.send(f"{command}\n")
            time.sleep(1)
            wait_for_command_output(shell, command, r'#', hostname, timeout, session_log_file)

    except Exception as e:
        verbose_print(f"{time.ctime()} - Failed to connect to {hostname}, check DNS/reachability.\n{e}\n")
        with open(f"logs/errors.log", "a") as file:
            file.write(f"{time.ctime()} - Failed to connect to {hostname}, check DNS reachability.\n{e}\n")
            file.write(traceback.format_exc() + "\n")
    finally:
        ssh.close()
        verbose_print(f"Connection closed.")

def process_host_file(file_path, username, password, enable_password, commands, timeout, max_threads=8):
    """
    Processes hosts concurrently using multi-threading.
    """
    with open(file_path, "r") as file:
        hostnames = file.read().splitlines()

    # -- Create a ThreadPoolExecutor to manage threads
    with ThreadPoolExecutor(max_threads) as executor:
        future_to_hostname = {
            executor.submit(connect_to_device, hostname, username, password, enable_password, commands, timeout): hostname
            for hostname in hostnames
        }

        for future in as_completed(future_to_hostname):
            hostname = future_to_hostname[future]
            try:
                # -- Get the result to ensure the task completed successfully
                future.result()
                verbose_print(f"Completed processing for {hostname}")
            except Exception as exc:
                verbose_print(f"Error processing {hostname}: {exc}")
                with open("logs/errors.log", "a") as file:
                    file.write(f"Error processing {hostname}: {exc}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process hostnames and commands.")
    parser.add_argument("-f", "--file", required=True, help="File containing list of hostnames")
    parser.add_argument("-c", "--commands", required=True, help="File containing list of commands")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout for prompts and enable checks (default: 10s)")
    parser.add_argument("--threads", type=int, default=8, help="Number of threads to use (default: 8)")
    args = parser.parse_args()

    verbose = args.verbose

    # -- Ensure directories exist here
    ensure_directory_exists("logs")
    ensure_directory_exists("configs")

    # -- Log everything to ssh.log
    paramiko.util.log_to_file('logs/ssh.log')

    username = input("Enter username: ")
    password = getpass("Enter password: ")
    enable_password = getpass("Enter enable password (if applicable, press Enter to skip): ") or password

    with open(args.commands, "r") as cmd_file:
        commands = cmd_file.read().splitlines()

    process_host_file(args.file, username, password, enable_password, commands, args.timeout, args.threads)
