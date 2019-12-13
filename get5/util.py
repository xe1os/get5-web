import os
import socket
import subprocess
import base64
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto import Random


def as_int(val, on_fail=0):
    if val is None:
        return on_fail
    try:
        return int(val)
    except ValueError:
        return on_fail


def format_mapname(mapname):
    formatted_names = {
        'de_cbble': 'Cobblestone',
        'de_dust2': 'Dust II',
    }
    if mapname in formatted_names:
        return formatted_names[mapname]
    else:
        de_map = mapname.startswith('de_')
        if de_map:
            return mapname[3:].title()
        else:
            return mapname


def check_server_connection(server, key=None):
    if key:
        decPass = decrypt(key, server.rcon_password)
    else:
        decPass = server.rcon_password
    response = send_rcon_command(
        server.ip_string, server.port, decPass, 'status')
    return response is not None


def check_server_avaliability(server, key=None):
    import json

    if not server:
        return None, 'Server not found'
    if key:
        encRcon = decrypt(key, server.rcon_password)
    else:
        encRcon = server.rcon_password
    response = send_rcon_command(
        server.ip_string, server.port, encRcon, 'get5_web_avaliable')

    if response:
        json_error = False
        already_live = False
        try:
            json_reply = json.loads(response)
            already_live = json_reply['gamestate'] != 0
        except (ValueError, KeyError):
            json_error = True

    if response is None:
        return None, 'Failed to connect to server'

    elif 'Unknown command' in str(response):
        return None, 'Either get5 or get5_apistats plugin missing'

    elif already_live:
        return None, 'Server already has a get5 match setup'

    elif json_error:
        return None, 'Error reading get5_web_avaliable response'

    else:
        return json_reply, ''


class RconError(ValueError):
    pass


def send_rcon_command(host, port, rcon_password, command,
                      raise_errors=False, num_retries=3, timeout=3.0):
    from valve.source.rcon import (RCON, IncompleteMessageError,
                                   AuthenticationError, NoResponseError)

    try:
        port = int(port)
    except ValueError:
        return None

    attempts = 0
    while attempts < num_retries:
        attempts += 1
        try:
            with RCON((host, port), rcon_password, timeout=timeout) as rcon:
                response = rcon(command)
                return strip_rcon_logline(response)

        except KeyError:
            # There seems to be a bug in python-vavle where a wrong password
            # trigger a KeyError at line 203 of valve/source/rcon.py,
            # so this is a work around for that.
            raise RconError('Incorrect rcon password')

        except (socket.error, socket.timeout,
                IncompleteMessageError, AuthenticationError, NoResponseError) as e:
            if attempts >= num_retries:
                if raise_errors:
                    raise RconError(str(e))
                else:
                    return None


def strip_rcon_logline(response):
    lines = response.splitlines()
    if len(lines) >= 1:
        last_line = lines[len(lines) - 1]
        if 'rcon from' in last_line:
            return '\n'.join(lines[:len(lines) - 1])

    return response


def get_version():
    try:
        root_dir = os.path.realpath(os.path.join(
            os.getcwd(), os.path.dirname(__file__), '..'))
        cmd = ['git', 'rev-parse', '--short', 'HEAD']
        return subprocess.check_output(cmd, cwd=root_dir).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def encrypt(key, source, encode=True):
    if not source:
        return
    # use SHA-256 over our key to get a proper-sized AES key
    key = SHA256.new(key).digest()
    IV = Random.new().read(AES.block_size)  # generate IV
    encryptor = AES.new(key, AES.MODE_CBC, IV)
    # calculate needed padding
    padding = AES.block_size - len(source) % AES.block_size
    # Python 2.x: source += chr(padding) * padding # Python 3.x
    # bytes([padding]) * padding
    source += chr(padding) * padding
    # store the IV at the beginning and encrypt
    data = IV + encryptor.encrypt(source)
    return base64.b64encode(data).decode("latin-1") if encode else data

# Try excepts are to avoid any backwards compatibility issues.


def decrypt(key, source, decode=True):
    if not source:
        return None
    if decode:
        try:
            source = base64.b64decode(source.encode("latin-1"))
        except:
            return None
    # use SHA-256 over our key to get a proper-sized AES key
    key = SHA256.new(key).digest()
    IV = source[:AES.block_size]  # extract the IV from the beginning
    try:
        decryptor = AES.new(key, AES.MODE_CBC, IV)
    except:
        return None
    data = decryptor.decrypt(source[AES.block_size:])  # decrypt
    # pick the padding value from the end; Python 2.x: ord(data[-1]) # Python
    # 3.x: data[-1]
    padding = ord(data[-1])
    # Python 2.x: chr(padding) * padding # Python 3.x: bytes([padding]) *
    # padding:
    if data[-padding:] != chr(padding) * padding:
        return None
    return data[:-padding]  # remove the padding

def is_server_owner(user, server):
    if user is None or server is None:
        return False
    elif user.id == server.user_id:
        return True
    else:
        return False

    return bool(user.admin)
