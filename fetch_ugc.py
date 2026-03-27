import paramiko

hostname = '46.225.212.66'
port = 22
username = 'root'
password = 'RhPAKeFbrvFm'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname, port, username, password, timeout=10)

commands = [
    "find /root -maxdepth 2 -type d",
    "find /home -maxdepth 2 -type d",
    "ls -la /root",
    "ls -la /var/www",
    "ls -la /opt"
]

print("Running broader directory search on server...\n")
for cmd in commands:
    print(f"--- {cmd} ---")
    stdin, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode('utf-8'))
    err = stderr.read().decode('utf-8')
    if err: print("ERR:", err)

client.close()
