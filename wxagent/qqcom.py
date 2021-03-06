
QQAGENT_SERVICE_NAME = 'io.qtc.qqagent'
QQAGENT_SEND_PATH = '/io/qtc/qqagent'
QQAGENT_IFACE_NAME = 'io.qtc.qqagent.iface'

QQAGENT_EVENT_BUS_PATH = '/io/qtc/qqagent/signals'
QQAGENT_EVENT_BUS_IFACE = 'io.qtc.qqagent.signals'


# TODO 交换CONNECTED值为1，其他值延后
CONN_STATE_NONE = 0
CONN_STATE_WANT_USERNAME = 1
CONN_STATE_WANT_PASSWORD = 2
CONN_STATE_CONNECTED = 3

# constant for QQ
QQ_CLIENTID = 53999199
QQ_POLL2_TIMEOUT = 60  # 秒
QQ_POLL2_TIMEOUT2 = 120  # 秒
QQ_APPID = "501004106"
QQ_DEVID = 'e669767113868187'

# QQ聊天会话类型
CHAT_TYPE_NONE = 0
CHAT_TYPE_U2U = 1
CHAT_TYPE_QUN = 2
CHAT_TYPE_DISCUS = 3
CHAT_TYPE_SESS = 4


# QQ 消息 poll_type类型
QQ_PT_NONE = 0
QQ_PT_SESSION = 1
QQ_PT_DISCUS = 2
QQ_PT_QUN = 3
QQ_PT_USER = 4
QQ_PT_KICK = 5
QQ_PT_STATUS = 6
QQ_PT_INPUT_NOTIFY = 7
QQ_PT_TIPS = 8
QQ_PT_FILE = 9
QQ_PT_SHAKE = 10
QQ_PT_AV_REQUEST = 11
QQ_PT_AV_REFUSE = 12


# QQ 消息 类型
QQMSG_TYPE_9 = 9  # 收到文件消息/shake
QQMSG_TYPE_43 = 43  # 抓图图片消息
