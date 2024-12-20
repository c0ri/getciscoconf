import paramiko
import time
import re
import argparse
from getpass import getpass
from datetime import datetime
import os

paramiko.util.log_to_file('logs/ssh.log')

# Define a global verbose flag
verbose = False

def ensure_directory_exists(directory):
    """Ensures the directory exists, creates it if not."""
    if not os.path.exists(directory):
        os.makedirs(directory)

def is_enabled(shell, timeout):
    start_time = time.time()
    buffer = ''
    print(f"Checking if we are enabled: ", end='')
    while time.time() - start_time < timeout:
        if shell.recv_ready():
            buffer += shell.recv(65535).decode('utf-8')
            if re.search(r'#', buffer):
                print(f"YES.")
                return True
            else:
                print(f"NO.")
                return False
        time.sleep(1)
    return False

def verbose_print(message):
    """Prints the message only if verbosity is enabled."""
    if verbose:
        print(message)

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
    Regular commands go to the session log, and 'show run' commands go to separate config files.
    """
    start_time = time.time()
    command_output = ''
    verbose_print(f"Running command: {command}")

    while time.time() - start_time < timeout:
        if shell.recv_ready():
            command_output += shell.recv(65535).decode('utf-8')
            if re.search(prompt, command_output):
                break
        time.sleep(1)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Handle 'show run' commands separately
    if "show run" in command.lower():
        sanitized_command = "config"
        ensure_directory_exists("configs")
        config_filename = f"configs/{hostname}-{timestamp}-{sanitized_command}.log"
        verbose_print(f"Saving 'show run' output to {config_filename}")
        with open(config_filename, "w") as file:
            file.write(command_output)
    else:
        # Save regular commands to the session log
        verbose_print(f"Appending command output to session log {session_log_file}")
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

        # Prepare session log file
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        session_log_file = f"logs/{hostname}-session-{timestamp}.log"
        ensure_directory_exists("logs")

        # Check if in enabled mode; if not, enter it
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

        # Process each command in the list
        for command in commands:
            shell.send(f"{command}\n")
            time.sleep(1)
            wait_for_command_output(shell, command, r'#', hostname, timeout, session_log_file)

    except Exception as e:
        verbose_print(f"{time.ctime()} - Failed to connect to {hostname}, check DNS/reachability.\n{e}\n")
        with open(f"logs/errors.log", "a") as file:
            file.write(f"{time.ctime()} - Failed to connect to {hostname}, check DNS reachability.\n{e}\n")
    finally:
        ssh.close()
        verbose_print(f"Connection closed.")

def process_host_file(file_path, username, password, enable_password, commands, timeout):
    with open(file_path, "r") as file:
        hostnames = file.read().splitlines()

    for hostname in hostnames:
        connect_to_device(hostname, username, password, enable_password, commands, timeout)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process hostnames and commands.")
    parser.add_argument("-f", "--file", required=True, help="File containing list of hostnames")
    parser.add_argument("-c", "--commands", required=True, help="File containing list of commands")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout for prompts and enable checks (default: 10s)")
    args = parser.parse_args()

    # Set the global verbose flag based on the -v switch
    verbose = args.verbose

    username = input("Enter username: ")
    password = getpass("Enter password: ")
    enable_password = getpass("Enter enable password (if applicable, press Enter to skip): ") or password

    with open(args.commands, "r") as cmd_file:
        commands = cmd_file.read().splitlines()

    process_host_file(args.file, username, password, enable_password, commands, args.timeout)
