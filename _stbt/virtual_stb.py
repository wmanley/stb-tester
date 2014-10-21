import os
import signal
import socket
import subprocess
from contextlib import contextmanager

from . import docker, notify, utils
from .config import set_config


@contextmanager
def virtual_stb(cmd, docker_image=None, share_x=True,
                with_lirc="/run/lirc/lircd"):
    with notify.sd_listen(dir_=os.environ['XDG_RUNTIME_DIR']) as listener, \
            open('virtual-stb.log', 'w') as logfile:
        utils.mkdir_p('/tmp/.X11-unix')
        if os.stat('/tmp/.X11-unix').st_mode & 0777 != 0777:
            os.chmod('/tmp/.X11-unix', 0777)
        if docker_image:
            docker_args = []
            if share_x:
                docker_args += ['-v', '/tmp/.X11-unix:/tmp/.X11-unix']

            vstb_cmd = (
                ['docker', 'run', '--rm=true',
                 '-v', '/etc/localtime:/etc/localtime:ro',
                 '-v', '%s:/run/stbt-virtual-stb/notify' %
                 docker.container_to_host_path(listener.socket_path),
                 '-e', 'NOTIFY_SOCKET=/run/stbt-virtual-stb/notify',
                 '--cidfile', '%s-cid' % listener.socket_path] + docker_args +
                [docker_image] + cmd)
        else:
            vstb_cmd = (
                ['python',
                 os.path.dirname(__file__) + '/virtual-stb-impl.py'] +
                (['--with-lirc'] if with_lirc else []) + cmd)

        child = subprocess.Popen(vstb_cmd, stdout=logfile, stderr=logfile)
        notify_data = {}

        def await_notification(key):
            while True:
                if key in notify_data:
                    return notify_data[key]
                if child.poll() is not None:
                    with open('virtual-stb.log', 'r') as f:
                        raise RuntimeError(
                            'virtual-stb died before notifying %s\n%s' % (
                                key, f.read()))
                try:
                    k, v = listener.read_msg(timeout=1)
                    notify_data[k] = v
                except socket.timeout:
                    pass

        display = await_notification('X_DISPLAY')
        set_config(
            'global', 'source_pipeline',
            'ximagesrc use-damage=false remote=true show-pointer=false '
            'display-name=%(x_display)s ! video/x-raw,framerate=24/1')
        set_config('global', 'x_display', display)

        await_notification('READY')

        if 'X_LIRC_SOCKET' in notify_data:
            set_config('global', 'control', 'lirc:%s:%s' % (
                await_notification('X_LIRC_SOCKET'),
                await_notification('X_LIRC_REMOTE_NAME')))
        else:
            set_config('global', 'control', 'x11:%(x_display)s')

        if 'X_HOST_ADDRESS' in notify_data:
            set_config('device_under_test', 'address',
                await_notification('X_HOST_ADDRESS'))

        if docker_image is not None:
            docker_cid = open('%s-cid' % listener.socket_path, 'r').read()
        else:
            docker_cid = ''

        try:
            yield (docker_cid, child, notify_data)
        finally:
            if docker_image:
                subprocess.call(['docker', 'kill', docker_cid])
            else:
                os.kill(child.pid, signal.SIGTERM)
