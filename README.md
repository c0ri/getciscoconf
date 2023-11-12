# GetCiscoConf
This is a simple Python script project to login to Cisco devices and download the running config.

# GetConf.py
This will take a file 'hostnames.txt' which a simple list of hostnames, one per line.  It will then connect to those and pull the running config and
save it to HOSTNAME-config on the local filesystem. The HOSTNAME is derived from the command 'sho run |i hostname'. Hopefully it's accurate but I
will probably add some code to ensure it later.
Be sure to change:
host_file_path = "hostnames.txt"  # Replace with your actual file path

# Requires 
Paramiko
Base64

The password is stored encoded as a Base64 text:
encoded_password_file = "encoded_password.txt"  # Replace with your actual file path

This is basic password protection for now, but you can proably mod this or I will later to use Passbolt's API to store the password and retreive it.

# Disclaimer
Your use of this software means that you accept whatever it does for good or bad. Read the source code and ensure it works properly with some testing before you go all out with it.
If something breaks, you own all the pieces.


