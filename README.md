# GetCiscoConf
This is a simple set of Python scripts to allow you to do useful things with Cisco IOS devices. Such as downloading a config, or running commands ad-hoc against a large number of devices.

# Last Update
2024-12-06 - Cleaned up logging.

# GetConf.py
This will take a file 'hostnames.txt' which a simple list of hostnames, one per line.  It will then connect to those and pull the running config and
save it to HOSTNAME-config on the local filesystem. The HOSTNAME is derived from the command 'sho run |i hostname'. Hopefully it's accurate but I
will probably add some code to ensure it later.
Be sure to change:
host_file_path = "hostnames.txt"  # Replace with your actual file path

# rungen.py
This script is a more generic script that will take a list of hosts and run a list of commands against them.
rungen.py Options:
    --file <hostlist> (a text file containing a list of hostnames or IPs, one per line.) 
    --commands <commandlist> (a text file containing a list of commands to run against each host from the --file option.
    --verbose  Prints output from everything the script is doing.
    --timeout  Optional argument that allows you to set a timeout. The default timeout is 10 seconds.

The script will save output as $HOSTNAME-$command-$TIME

It should sanitize the filename before it saves. This is a security feature but can probably be improved. Just be aware of that. I hope to tweak this and make it better in the future.

# Requires 
Paramiko

The password is stored encoded as a Base64 text:
encoded_password_file = "encoded_password.txt"  # Replace with your actual file path

This is basic password protection for now, but you can proably mod this or I will later to use Passbolt's API to store the password and retreive it.

NOTE: This is deprecated in the new rungen.py script. It's recommended to only use that script. Security wise, storing your passwords in any form is a bad idea.

# Disclaimer
Your use of this software means that you accept whatever it does for good or bad. Read the source code and ensure it works properly with some testing before you go all out with it.
If something breaks, you own all the pieces.


