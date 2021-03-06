# coding=utf8
import os
import sys
import re
import uuid
import json
import requests
import redis

import datetime
import socket

from eventlet import event
from eventlet import greenthread

from ops_sia import cache
from ops_sia.options import get_options
from ops_sia import log as logging
from ops_sia import exception

options = get_options()

LOG = logging.getLogger(__name__)


def import_class(import_str):
    """Returns a class from a string including module and class."""
    mod_str, _sep, class_str = import_str.rpartition('.')
    try:
        __import__(mod_str)
        return getattr(sys.modules[mod_str], class_str)
    except (ImportError, ValueError, AttributeError), exc:
        LOG.debug('Inner Exception: %s', exc)
        raise exception.ClassNotFound(class_name=class_str, exception=exc)


def utcnow():
    """Overridable version of utils.utcnow."""
    return datetime.datetime.utcnow()


def import_object(import_str):
    """Returns an object including a module or module and class."""
    try:
        __import__(import_str)
        return sys.modules[import_str]
    except ImportError:
        cls = import_class(import_str)
        return cls()


def cleanup_file_locks():
    """clean up stale locks left behind by process failures

    The lockfile module, used by @synchronized, can leave stale lockfiles
    behind after process failure. These locks can cause process hangs
    at startup, when a process deadlocks on a lock which will never
    be unlocked.

    Intended to be called at service startup.

    """

    hostname = socket.gethostname()
    sentinel_re = hostname + r'-.*\.(\d+$)'
    lockfile_re = r'ops_sia-.*\.lock'
    files = os.listdir(options.lock_path)

    # cleanup sentinels
    for filename in files:
        match = re.match(sentinel_re, filename)
        if match is None:
            continue
        pid = match.group(1)
        LOG.debug('Found sentinel %(filename)s for pid %(pid)s' %
                  {'filename': filename, 'pid': pid})
        try:
            os.kill(int(pid), 0)
        except OSError, e:
            # PID wasn't found
            delete_if_exists(os.path.join(FLAGS.lock_path, filename))
            LOG.debug('Cleaned sentinel %(filename)s for pid %(pid)s' %
                      {'filename': filename, 'pid': pid})

    # cleanup lock files
    for filename in files:
        match = re.match(lockfile_re, filename)
        if match is None:
            continue
        try:
            stat_info = os.stat(os.path.join(FLAGS.lock_path, filename))
        except OSError as e:
            if e.errno == errno.ENOENT:
                continue
            else:
                raise
        msg = ('Found lockfile %(file)s with link count %(count)d' %
               {'file': filename, 'count': stat_info.st_nlink})
        LOG.debug(msg)
        if stat_info.st_nlink == 1:
            delete_if_exists(os.path.join(FLAGS.lock_path, filename))
            msg = ('Cleaned lockfile %(file)s with link count %(count)d' %
                   {'file': filename, 'count': stat_info.st_nlink})
            LOG.debug(msg)


class LoopingCall(object):
    def __init__(self, f=None, *args, **kw):
        self.args = args
        self.kw = kw
        self.f = f
        self._running = False

    def start(self, interval, now=True):
        self._running = True
        done = event.Event()

        def _inner():
            if not now:
                greenthread.sleep(interval)
            try:
                while self._running:
                    self.f(*self.args, **self.kw)
                    if not self._running:
                        break
                    greenthread.sleep(interval)
            except LoopingCallDone, e:
                self.stop()
                done.send(e.retvalue)
            except Exception:
                LOG.exception('in looping call')
                done.send_exception(*sys.exc_info())
                return
            else:
                done.send(True)

        self.done = done

        greenthread.spawn(_inner)
        return self.done

    def stop(self):
        self._running = False

    def wait(self):
        return self.done.wait()


class LoopingCallDone(Exception):
    """Exception to break out and stop a LoopingCall.

    The poll-function passed to LoopingCall can raise this exception to
    break out of the loop normally. This is somewhat analogous to
    StopIteration.

    An optional return-value can be included as the argument to the exception;
    this return-value will be returned by LoopingCall.wait()

    """

    def __init__(self, retvalue=True):
        """:param retvalue: Value that LoopingCall.wait() should return."""
        self.retvalue = retvalue


def get_uuid(uuid_str):
    uuid_re = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    uuid_str = re.findall(r'%s' % uuid_re, uuid_str)
    if uuid_str:
        return uuid_str[0]


def generate_uuid(uuid_str):
    return str(uuid.uuid3(uuid.NAMESPACE_OID, (uuid_str.encode('utf8'))))


def get_http(url='/', data='', method='get', headers={}, files=''):
    request = getattr(requests, method)
    return request(url, data=data, headers=headers, files=files, verify=False)


def post_http(url='/', data='', method='post', headers={}, files=''):
    post = getattr(requests, method)
    return post(url, data=data, headers=headers, files=files, verify=False)


def put_http(url='/', data='', method='put', headers={}, files=''):
    put = getattr(requests, method)
    return put(url, data=data, headers=headers, files=files, verify=False)


def patch_http(url='/', data='', method='patch', headers={}, files=''):
    patch = getattr(requests, method)
    return patch(url, data=data, headers=headers, files=files, verify=False)


def get_token(username=options.username, password=options.password, tenant=options.tenant):
    backend = cache.Backend()
    if tenant:
        token = backend.get("keystone_tenant_endpoint")
        if not token:
            data = {"auth":
                        {"passwordCredentials":
                             {"username": username,
                              "password": password},
                         'tenantName': tenant
                         },
                    }
            r = post_http(method='post', url='%s/tokens' % options.keystone_admin_endpoint,
                          data=json.dumps(data))
            if r.status_code == 200 and r.json().get('access', ''):
                token = r.json().get('access').get("token").get("id")
                backend.set("keystone_tenant_endpoint", token)
                return r.json()['access']['token']['id']
            else:
                return False
        return token
    else:
        token = backend.get("keystone_admin_endpoint")
        if not token:
            data = {"auth":
                        {"passwordCredentials":
                             {"username": options.username,
                              "password": options.password
                              },
                         "tenantName": options.tenant}
                         }
            try:
                # first get token from redis. if not get from keystone
                r = post_http(method='post', url='%s/tokens' % options.keystone_admin_endpoint,
                              data=json.dumps(data))
                data = r.json()
                if r.status_code == 200 and data.get("access"):
                    token = data.get('access').get("token").get("id")
                    if not token:
                        em = "can not get admin token"
                        LOG.exception(em)
                        return False
                    backend.set("keystone_admin_endpoint", token)
                    return token
                else:
                    return False
            except Exception as e:
                LOG.exception(e)
                return False
        return token


def ip_into_int(ip):
    try:
        return reduce(lambda x, y: (x << 8) + y, map(int, ip.split('.')))
    except:
        return 0


def is_internal_ip(ip):
    ip = ip_into_int(ip)
    net_a = ip_into_int('10.255.255.255') >> 24
    net_b = ip_into_int('172.16.255.255') >> 20
    net_c = ip_into_int('192.168.255.255') >> 16
    net_d = ip_into_int('127.255.255.255') >> 24
    net_e = ip_into_int('169.254.255.255') >> 16
    net_f = ip_into_int('224.255.255.255') >> 24
    net_g = ip_into_int('127.255.255.255') >> 24

    return ip >> 24 == net_a or \
           ip >> 20 == net_b or \
           ip >> 16 == net_c or \
           ip >> 24 == net_d or \
           ip >> 16 == net_e or \
           ip >> 24 == net_f or \
           ip >> 24 == net_g


def match_ip(ip):
    return re.findall(r'[0-9]+(?:\.[0-9]+){3}', ip)[0]


def parse_url(host, path="/", port=80, protocol="http", **kwargs):
    """生成url"""
    args = ""
    if not kwargs:
        return protocol + "://" + host + ":" + str(port) + path
    for k, v in kwargs.items():
        temp_str = str(k) + "=" + str(v) + "&"
        args += temp_str
    url = protocol + "://" + host + ":" + str(port) + path + "?" + args
    return url[:-1]


if __name__ == '__main__':
    print is_internal_ip('10.2.83.162')
