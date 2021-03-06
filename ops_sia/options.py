# coding=utf8

"""
every opt of used should bu define first


this options is based on tornado.options
"""

from tornado.options import define, parse_command_line, \
    parse_config_file, options

common_opts = [
    {
        "name": 'debug',
        "default": False,
        "help": 'if logged debug info',
        "type": bool,
    },
    {
        "name": 'verbose',
        "default": False,
        "help": 'if log detail',
        "type": bool,
    },
    {
        "name": 'config',
        "default": '/etc/sia/ops_sia.conf',
        "help": 'path of config file',
        "type": str,
        "callback": lambda path: parse_config_file(path, final=False)
    },
    {
        "name": 'sql_connection',
        "default": 'mysql+mysqlconnector://root:123456@127.0.0.1/charging?charset=utf8',
        "help": 'The SQLAlchemy connection string used to connect to \
                    the database',
        "type": str,
    },
    {
        "name": 'db_driver',
        "default": 'ops_sia.db.api',
        "help": 'default db driver',
        "type": str,
    },
    {
        "name": 'lock_path',
        "default": '/var/lock',
        "help": 'path of config file',
        "type": str,
    },
    {
        "name": 'api_port',
        "default": 8901,
        "help": 'listen port of api',
        "type": int,
    },
    {
        "name": 'listen',
        "default": '127.0.0.1',
        "help": 'listen address',
        "type": str,
    },
    {
        "name": 'keystone_admin_endpoint',
        "default": '',
        "help": 'the keystone endpoint url',
        "type": str,
    },
    {
        "name": 'keystone_endpoint',
        "default": '',
        "help": 'the keystone endpoint url',
        "type": str,
    },
    {
        "name": 'username',
        "default": 'admin',
        "help": 'username of auth',
        "type": str,
    },
    {
        "name": 'password',
        "default": '',
        "help": 'password of auth',
        "type": str,
    },
    {
        "name": 'extra_opts',
        "default": '',
        "help": "all opts of app's",
        "type": str,
    },
    {
        "name": 'tenant',
        "default": 'admin',
        "help": "all opts of app's",
        "type": str,
    },
    {
        "name": 'old_keystone_admin_endpoint',
        "default": 'http://10.2.0.61:8092/ecapi/check_pass',
        "help": "old platform",
        "type": str,
    },
    {
        "name": 'sms_api_key',
        "default": 0,
        "help": "sms api auth key",
        "type": str,
    },
    {
        "name": 'code_auth_len',
        "default": '',
        "help": "code auth len",
        "type": int,
    },
    {
        "name": 'auth_code_valid_time',
        "default": 0,
        "help": "code auth len",
        "type": int,
    },
    {
        "name": 'sms_auth_code_len',
        "default": 0,
        "help": "code auth len",
        "type": int,
    },
    {
        "name": 'sms_msg_template',
        "default": "",
        "help": "code auth len",
        "type": str,
    },
    {
        "name": 'auth_code_interval',
        "default": "",
        "help": "code auth len",
        "type": int,
    },
    {
        "name": 'roles_ep',
        "default": "",
        "help": "code auth len",
        "type": str,
    },
    {
        "name": 'project_ep',
        "default": "",
        "help": "code auth len",
        "type": str,
    },
    {
        "name": 'user_ep',
        "default": "",
        "help": "code auth len",
        "type": str,
    },
    {
        "name": 'cmdb_host',
        "default": "",
        "help": "code auth len",
        "type": str,
    },
    {
        "name": 'cmdb_port',
        "default": "",
        "help": "code auth len",
        "type": int,
    },
    # 发送短信的消息类型
    {
        "name": 'sms_real_name_auth_template',
        "default": "",
        "help": "",
        "type": str,
    },
    {
        "name": 'file_path',
        "default": "",
        "help": "",
        "type": str,
    },
    {
        "name": 'floting_ip',
        "default": "",
        "help": "",
        "type": str,
    },
    {
        "name": 'wechat_ep',
        "default": "",
        "help": "",
        "type": str,
    },
    {
        "name": 'wechat_realname_auth_notify',
        "default": [],
        "help": "",
        "type": list,
    },
    {
        "name": 'worder_ep',
        "default": "",
        "help": "",
        "type": str,
    },
    {
        "name": 'cmdb_ep',
        "default": "",
        "help": "",
        "type": str,
    },
    {
        "name": 'sync_api',
        "default": "",
        "help": "",
        "type": str,
    },
    {
        "name": 'api_gateway_url',
        "default": "",
        "help": "",
        "type": str,
    },
]



def register_opt(opt, group=None):
    """Register an option schema
    opt = {
            "name": 'config',
            "default": 'ops_sia.conf',
            "help": 'path of config file',
            "tyle": str,
            "callback": lambda path: parse_config_file(path, final=False)
        }
    """
    if opt.get('name', ''):
        optname = opt.pop('name')
        if optname in options._options.keys():
            options._options.pop(optname)
        define(optname, **opt)


def register_opts(opts, group=None):
    """Register multiple option schemas at once."""
    for opt in opts:
        register_opt(opt, group)
    return options


def get_options(opts=None, group=None):
    if opts:
        register_opts(opts, group)
    options = register_opts(common_opts, 'common')
    if options.as_dict().get('extra_opts', ''):
        try:
            extra_opts = __import__(options.extra_opts)
            options = register_opts(extra_opts.config.opts, 'extra')
        except Exception as e:
            print "get config error msg %r" % e
    parse_config_file(options.config, final=False)
    parse_command_line()
    return options


if __name__ == "__main__":
    print get_options().as_dict()
    options = get_options()
    print options.get('sql_connection', None)
