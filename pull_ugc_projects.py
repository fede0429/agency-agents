import paramiko

hostname = '46.225.212.66'
port = 22
username = 'root'
password = 'RhPAKeFbrvFm'

print("Connecting to Hetzner...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname, port, username, password, timeout=10)

print("Compressing on server (this could take a minute)...")
stdin, stdout, stderr = client.exec_command("cd /opt && tar -czf ugc_anime_projects.tar.gz ugc-video-pro Toonflow-app")
out = stdout.read().decode('utf-8')
err = stderr.read().decode('utf-8')
if out: print("OUT:", out)
if err: print("ERR:", err)

print("Downloading to local scratch...")
sftp = client.open_sftp()
local = "C:\\Users\\federico\\.gemini\\antigravity\\scratch\\ugc_anime_projects.tar.gz"
sftp.get('/opt/ugc_anime_projects.tar.gz', local)
sftp.close()
client.close()
print("Done!")
