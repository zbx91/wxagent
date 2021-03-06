# web qq protocol

import os, sys
import json, re
import enum
import time

from PyQt5.QtCore import *
from PyQt5.QtNetwork import *
from PyQt5.QtDBus import *

from .imrelayfactory import IMRelayFactory
from .qqcom import *
from .qqsession import *
from .unimessage import *
from .filestore import QiniuFileStore, VnFileStore

from .tx2any import TX2Any, Chatroom


#
#
#
class WX2Tox(TX2Any):

    def __init__(self, parent=None):
        "docstring"
        super(WX2Tox, self).__init__(parent)

        self.agent_service = QQAGENT_SERVICE_NAME
        self.agent_service_path = QQAGENT_SEND_PATH
        self.agent_service_iface = QQAGENT_IFACE_NAME
        self.agent_event_path = QQAGENT_EVENT_BUS_PATH
        self.agent_event_iface = QQAGENT_EVENT_BUS_IFACE
        self.relay_src_pname = 'WQU'

        self.initDBus()
        self.initRelay()
        self.startWXBot()
        return

    # @param msg str
    def uicmdHandler(self, msg):

        if msg[0] != "'":
            qDebug('not a uicmd, normal msg, omit for now.')
            return

        if msg.startswith("'help"):
            friendId = self.peerToxId
            uicmds = ["'help", "'qqnum <num>", "'passwd <pwd[|vfcode]>'", ]
            self.peerRelay.sendMessage("\n".join(uicmds), self.peerRelay.peer_user)
            pass
        elif msg.startswith("'qqnum"):
            qqnum = msg[6:].strip()
            qDebug('the qqnum is:' + str(qqnum))
            self.sendQQNum(qqnum)
            pass
        elif msg.startswith("'passwd"):
            passwd, *vfcode = msg[8:].strip().split('|')
            if len(vfcode) == 0: vfcode.append(4567)
            vfcode = vfcode[0]
            self.sendPasswordAndVerify(passwd, vfcode)
            pass
        else:
            qDebug('unknown uicmd:' + msg[0:120])

        return

    def startWXBot(self):

        cstate = self.getConnState()
        qDebug('curr conn state:' + str(cstate))

        need_send_notify = False
        notify_msg = ''

        if cstate == CONN_STATE_NONE:
            # do nothing
            qDebug('wait for qqagent bootup...')
            QTimer.singleShot(2345, self.startWXBot)
            pass
        elif cstate == CONN_STATE_WANT_USERNAME:
            need_send_notify = True
            notify_msg = "Input qqnum: ('qqnum <1234567>)"
            pass
        elif cstate == CONN_STATE_WANT_PASSWORD:
            need_send_notify = True
            notify_msg = "Input password: ('passwd <yourpassword>)"
            pass
        elif cstate == CONN_STATE_CONNECTED:
            qDebug('qqagent already logined.')
            self.createWXSession()
            pass
        else:
            qDebug('not possible.')
            pass

        if need_send_notify is True:
            # TODO 这里有一个时序问题，有可能self.peerRelay为None，即relay还没有完全启动
            # time.sleep(1)  # hotfix lsself.peerRelay's toxkit is None sometime.
            tkc = self.peerRelay.isPeerConnected(self.peerRelay.peer_user)
            if tkc is True:
                self.peerRelay.sendMessage(notify_msg, self.peerRelay.peer_user)
            else:
                self.notify_buffer.append(notify_msg)
                self.need_send_notify = True

        self.sendQRToRelayPeer()
        # if logined is True: self.createWXSession()
        return

    @pyqtSlot(QDBusMessage)
    def onDBusWantQQNum(self, message):
        qDebug(str(message.arguments()))
        self.startWXBot()  # TODO 替换成登陆状态机方法
        return

    # @param a0=needvfc
    # @param a1=vfcpic
    @pyqtSlot(QDBusMessage)
    def onDBusWantPasswordAndVerifyCode(self, message):
        qDebug(str(message.arguments()))

        need_send_notify = False
        notify_msg = ''

        cstate = CONN_STATE_WANT_PASSWORD
        assert(cstate == CONN_STATE_WANT_PASSWORD)

        need_send_notify = True
        notify_msg = "Input password: ('passwd <yourpassword>)"

        if need_send_notify is True:
            tkc = False
            tkc = self.peerRelay.isPeerConnected(self.peerRelay.peer_user)
            qDebug(str(tkc))
            if tkc is True:
                self.peerRelay.sendMessage(notify_msg, self.peerRelay.peer_user)
            else:
                self.notify_buffer.append(notify_msg)
                self.need_send_notify = True

        return

    @pyqtSlot(QDBusMessage)
    def onDBusNewMessage(self, message):
        # qDebug(str(message.arguments()))
        args = message.arguments()
        msglen = args[0]
        msghcc = args[1]

        if self.txses is None: self.createWXSession()

        for arg in args:
            if type(arg) == int:
                qDebug(str(type(arg)) + ',' + str(arg))
            else:
                qDebug(str(type(arg)) + ',' + str(arg)[0:120])

        hcc64_str = args[1]
        hcc64 = hcc64_str.encode('utf8')
        hcc = QByteArray.fromBase64(hcc64)

        self.saveContent('qqmsgfromdbus.json', hcc)

        wxmsgvec = QQMessageList()
        wxmsgvec.setMessage(hcc)

        strhcc = hcc.data().decode('utf8')
        qDebug(strhcc[0:120].replace("\n", "\\n"))
        jsobj = json.JSONDecoder().decode(strhcc)

        # temporary send to friend
        # self.toxkit.sendMessage(self.peerToxId, strhcc)

        #############################
        # AddMsgCount = jsobj['AddMsgCount']
        # ModContactCount = jsobj['ModContactCount']

        # grnames = self.wxproto.parseWebSyncNotifyGroups(hcc)
        # self.txses.addGroupNames(grnames)

        # self.txses.parseModContact(jsobj['ModContactList'])

        msgs = wxmsgvec.getContent()
        for msg in msgs:
            fromUser = self.txses.getUserByName(msg.FromUserName)
            toUser = self.txses.getUserByName(msg.ToUserName)
            # qDebug(str(fromUser))
            # qDebug(str(toUser))
            if fromUser is None: qDebug('can not found from user object')
            if toUser is None: qDebug('can not found to user object')
            msg.FromUser = fromUser
            msg.ToUser = toUser

            # hot fix file ack
            # {'value': {'mode': 'send_ack', 'reply_ip': 183597272, 'time': 1444550216, 'type': 101, 'to_uin': 1449732709, 'msg_type': 10, 'session_id': 27932, 'from_uin': 1449732709, 'msg_id': 47636, 'inet_ip': 0, 'msg_id2': 824152}, 'poll_type': 'file_message'}
            if msg.FromUserName == msg.ToUserName:
                qDebug('maybe send_ack msg, but dont known how process it, just omit.')
                continue

            self.sendMessageToToxByType(msg)
        return

    def sendMessageToToxByType(self, msg):

        umsg = self.peerRelay.unimsgcls.fromQQMessage(msg, self.txses)
        logstr = umsg.get()
        dlogstr = umsg.dget()
        qDebug(dlogstr.encode())

        if msg.isOffpic():
            qDebug(msg.offpic)
            self.sendShotPicMessageToTox(msg, logstr)
        elif msg.isFileMsg():
            qDebug(msg.FileName.encode())
            self.sendFileMessageToTox(msg, logstr)
        else:
            self.sendMessageToTox(msg, logstr)
        return

    def dispatchToToxGroup(self, msg, fmtcc):

        if msg.FromUserName == 'newsapp':
            qDebug('special chat: newsapp')
            self.dispatchNewsappChatToTox(msg, fmtcc)
            pass
        elif msg.ToUserName == 'filehelper' or msg.FromUserName == 'filehelper':
            qDebug('special chat: filehelper')
            self.dispatchFileHelperChatToTox(msg, fmtcc)
            pass
        elif msg.PollType == QQ_PT_SESSION:
            qDebug('qq sess chat')
            self.dispatchQQSessChatToTox(msg, fmtcc)
            pass
        elif msg.FromUser.isGroup() or msg.ToUser.isGroup():
            # msg.ToUserName.startswith('@@') or msg.FromUserName.startswith('@@'):
            qDebug('wx group chat:')
            # wx group chat
            self.dispatchWXGroupChatToTox(msg, fmtcc)
            pass
        else:
            qDebug('u2u group chat:')
            # user <=> user
            self.dispatchU2UChatToTox(msg, fmtcc)
            pass

        return

    def dispatchNewsappChatToTox(self, msg, fmtcc):
        groupchat = None
        mkey = None
        title = ''

        mkey = 'newsapp'
        title = 'newsapp@WQU'

        if mkey in self.txchatmap:
            groupchat = self.txchatmap[mkey]
            # assert groupchat is not None
            # 有可能groupchat已经就绪，但对方还没有接收请求，这时发送失败，消息会丢失
            number_peers = self.peerRelay.groupNumberPeers(groupchat.group_number)
            if number_peers < 2:
                groupchat.unsend_queue.append(fmtcc)
                ### reinvite peer into group
                self.peerRelay.groupInvite(groupchat.group_number, self.peerRelay.peer_user)
            else:
                self.peerRelay.sendGroupMessage(fmtcc, groupchat.group_number)
        else:
            groupchat = self.createChatroom(msg, mkey, title)
            groupchat.unsend_queue.append(fmtcc)

        return

    def dispatchFileHelperChatToTox(self, msg, fmtcc):
        groupchat = None
        mkey = None
        title = ''

        if msg.FromUserName == 'filehelper':
            mkey = msg.FromUser.Uin
            title = '%s@WQU' % msg.FromUser.NickName
        else:
            mkey = msg.ToUser.Uin
            title = '%s@WQU' % msg.ToUser.NickName

        if mkey in self.txchatmap:
            groupchat = self.txchatmap[mkey]
            # assert groupchat is not None
            # 有可能groupchat已经就绪，但对方还没有接收请求，这时发送失败，消息会丢失
            number_peers = self.peerRelay.groupNumberPeers(groupchat.group_number)
            if number_peers < 2:
                groupchat.unsend_queue.append(fmtcc)
                ### reinvite peer into group
                self.peerRelay.groupInvite(groupchat.group_number, self.peerRelay.peer_user)
            else:
                self.peerRelay.sendGroupMessage(fmtcc, groupchat.group_number)
        else:
            groupchat = self.createChatroom(msg, mkey, title)
            groupchat.unsend_queue.append(fmtcc)

        return

    def dispatchWXGroupChatToTox(self, msg, fmtcc):
        groupchat = None
        mkey = None
        title = ''

        # TODO 这段代码好烂，在外层直接用的变量，到内层又检测是否为None，晕了
        if msg.FromUser.isGroup():
            if msg.FromUser is None:
                # message pending and try get group info
                qDebug('warning FromUser not found, wxgroup not found:' + msg.FromUserName)
                if msg.FromUserName in self.pendingGroupMessages:
                    self.pendingGroupMessages[msg.FromUserName].append([msg,fmtcc])
                else:
                    self.pendingGroupMessages[msg.ToUserName] = list()
                    self.pendingGroupMessages[msg.ToUserName].append([msg,fmtcc])

                # QTimer.singleShot(1, self.getBatchGroupAll)
                return
            else:
                mkey = msg.FromUser.Uin
                title = '%s@WQU' % msg.FromUser.NickName
                if len(msg.FromUser.NickName) == 0:
                    qDebug('maybe a temp group and without nickname')
                    title = 'TGC%s@WQU' % msg.FromUser.Uin
        else:
            if msg.ToUser is None:
                qDebug('warning ToUser not found, wxgroup not found:' + msg.ToUserName)
                if msg.FromUserName in self.pendingGroupMessages:
                    self.pendingGroupMessages[msg.ToUserName].append([msg,fmtcc])
                else:
                    self.pendingGroupMessages[msg.ToUserName] = list()
                    self.pendingGroupMessages[msg.ToUserName].append([msg,fmtcc])

                # QTimer.singleShot(1, self.getBatchGroupAll)
                return
            else:
                mkey = msg.ToUser.Uin
                title = '%s@WQU' % msg.ToUser.NickName
                if len(msg.ToUser.NickName) == 0:
                    qDebug('maybe a temp group and without nickname')
                    title = 'TGC%s@WQU' % msg.ToUser.Uin

        if mkey in self.txchatmap:
            groupchat = self.txchatmap[mkey]
            # assert groupchat is not None
            # 有可能groupchat已经就绪，但对方还没有接收请求，这时发送失败，消息会丢失
            number_peers = self.peerRelay.groupNumberPeers(groupchat.group_number)
            if number_peers < 2:
                groupchat.unsend_queue.append(fmtcc)
                ### reinvite peer into group
                self.peerRelay.groupInvite(groupchat.group_number, self.peerRelay.peer_user)
            else:
                self.peerRelay.sendGroupMessage(fmtcc, groupchat.group_number)
        else:
            # TODO 如果是新创建的groupchat，则要等到groupchat可用再发，否则会丢失消息
            groupchat = self.createChatroom(msg, mkey, title)
            groupchat.unsend_queue.append(fmtcc)

        return

    def dispatchWXGroupChatToTox2(self, msg, fmtcc, GroupUser):
        if msg.FromUser is None: msg.FromUser = GroupUser
        elif msg.ToUser is None: msg.ToUser = GroupUser
        else: qDebug('wtf???...')

        self.dispatchWXGroupChatToTox(msg, fmtcc)
        return

    def dispatchQQSessChatToTox(self, msg, fmtcc):
        groupchat = None
        mkey = None
        title = ''

        # 如果来源User没有找到，则尝试新请求获取group_sig，则首先获取临时会话的peer用户信息
        # 如果来源User没有找到，则尝试新请求获取好友信息
        to_uin = None
        if msg.FromUser is None:
            to_uin = msg.FromUserName
        elif msg.ToUser is None:
            to_uin = msg.ToUserName
        else:
            pass

        if to_uin is not None:
            pcall = self.sysiface.asyncCall('getfriendinfo', to_uin, 'a0', 123, 'a1')
            watcher = QDBusPendingCallWatcher(pcall)
            watcher.finished.connect(self.onGetFriendInfoDone)
            self.asyncWatchers[watcher] = [msg, fmtcc]
            return

        mkey = msg.ToUser.Uin
        title = '%s@WQU' % msg.ToUser.NickName
        if len(msg.ToUser.NickName) == 0:
            qDebug('maybe a temp group and without nickname')
            title = 'TGC%s@WQU' % msg.ToUser.Uin

        if mkey in self.txchatmap:
            groupchat = self.txchatmap[mkey]
            # assert groupchat is not None
            # 有可能groupchat已经就绪，但对方还没有接收请求，这时发送失败，消息会丢失
            number_peers = self.peerRelay.groupNumberPeers(groupchat.group_number)
            if number_peers < 2:
                groupchat.unsend_queue.append(fmtcc)
                ### reinvite peer into group
                self.peerRelay.groupInvite(groupchat.group_number, self.peerRelay.peer_user)
            else:
                self.peerRelay.sendGroupMessage(fmtcc, groupchat.group_number)
        else:
            # TODO 如果是新创建的groupchat，则要等到groupchat可用再发，否则会丢失消息
            groupchat = self.createChatroom(msg, mkey, title)
            groupchat.unsend_queue.append(fmtcc)

        return

    def dispatchU2UChatToTox(self, msg, fmtcc):
        groupchat = None
        mkey = None
        title = ''

        # 两个用户，正反向通信，使用同一个groupchat，但需要找到它
        if msg.FromUser.Uin == self.txses.me.Uin:
            mkey = msg.ToUser.Uin
            title = '%s@WQU' % msg.ToUser.NickName
        else:
            mkey = msg.FromUser.Uin
            title = '%s@WQU' % msg.FromUser.NickName

        # TODO 可能有一个计算交集的函数吧
        if mkey in self.txchatmap:
            groupchat = self.txchatmap[mkey]

        if groupchat is not None:
            # assert groupchat is not None
            # 有可能groupchat已经就绪，但对方还没有接收请求，这时发送失败，消息会丢失
            number_peers = self.peerRelay.groupNumberPeers(groupchat.group_number)
            if number_peers < 2:
                groupchat.unsend_queue.append(fmtcc)
                ### reinvite peer into group
                self.peerRelay.groupInvite(groupchat.group_number, self.peerRelay.peer_user)
            else:
                self.peerRelay.sendGroupMessage(fmtcc, groupchat.group_number)
        else:
            groupchat = self.createChatroom(msg, mkey, title)
            groupchat.unsend_queue.append(fmtcc)

        return

    def createChatroom(self, msg, mkey, title):

        group_number = ('WQU.%s' % mkey).lower()
        group_number = self.peerRelay.createChatroom(mkey, title)
        groupchat = Chatroom()
        groupchat.group_number = group_number
        groupchat.FromUser = msg.FromUser
        groupchat.ToUser = msg.ToUser
        groupchat.FromUserName = msg.FromUserName
        self.txchatmap[mkey] = groupchat
        self.relaychatmap[group_number] = groupchat
        groupchat.title = title

        if msg.PollType == QQ_PT_DISCUS:
            groupchat.chat_type = CHAT_TYPE_DISCUS
        elif msg.PollType == QQ_PT_QUN:
            groupchat.chat_type = CHAT_TYPE_QUN
        elif msg.PollType == QQ_PT_SESSION:
            groupchat.chat_type = CHAT_TYPE_SESS 
        elif msg.PollType == QQ_PT_USER:
            groupchat.chat_type = CHAT_TYPE_U2U
        else:
            qDebug('undefined behavior')

        groupchat.Gid = msg.Gid
        groupchat.ServiceType = msg.ServiceType

        self.peerRelay.groupInvite(group_number, self.peerRelay.peer_user)

        return groupchat

    def sendMessageToWX(self, groupchat, mcc):
        qDebug('here')

        FromUser = groupchat.FromUser
        ToUser = groupchat.ToUser

        if groupchat.chat_type == CHAT_TYPE_QUN:
            qDebug('send wx group chat:')
            # wx group chat
            self.sendWXGroupChatMessageToWX(groupchat, mcc)
            pass
        elif groupchat.chat_type == CHAT_TYPE_DISCUS:
            qDebug('send wx discus chat:')
            # wx discus chat
            self.sendWXDiscusChatMessageToWX(groupchat, mcc)
            pass
        elif groupchat.chat_type == CHAT_TYPE_SESS:
            qDebug('send wx sess chat:')
            # wx sess chat
            self.sendWXSessionChatMessageToWX(groupchat, mcc)
            pass
        elif groupchat.chat_type == CHAT_TYPE_U2U:
            qDebug('send wx u2u chat:')
            # user <=> user
            self.sendU2UMessageToWX(groupchat, mcc)
            pass
        elif ToUser.isGroup() or FromUser.isGroup():
            qDebug('send wx group chat:')
            # wx group chat
            self.sendWXGroupChatMessageToWX(groupchat, mcc)
            pass
        elif ToUser.isDiscus() or FromUser.isDiscus():
            qDebug('send wx discus chat:')
            # wx group chat
            self.sendWXDiscusChatMessageToWX(groupchat, mcc)
            pass
        else:
            qDebug('unknown chat:')
            pass

        # TODO 把从各群组来的发给WX端的消息，再发送给tox汇总端一份。

        if True: return
        from_username = groupchat.FromUser.UserName
        to_username = groupchat.ToUser.UserName
        args = [from_username, to_username, mcc, 1, 'more', 'even more']
        reply = self.sysiface.call('sendmessage', *args)  # 注意把args扩展开

        rr = QDBusReply(reply)
        if rr.isValid():
            qDebug(str(len(rr.value())) + ',' + str(type(rr.value())))
        else:
            qDebug('rpc call error: %s,%s' % (rr.error().name(), rr.error().message()))

        ### TODO send message faild

        return

    def sendWXGroupChatMessageToWX(self, groupchat, mcc):

        from_username = groupchat.FromUser.UserName
        to_username = groupchat.ToUser.UserName
        group_code = groupchat.ToUser.Uin

        args = [to_username, from_username, mcc, group_code, 1, 'more', 'even more']
        reply = self.sysiface.call('send_qun_msg', *args)  # 注意把args扩展开

        rr = QDBusReply(reply)
        if rr.isValid():
            qDebug(str(rr.value()) + ',' + str(type(rr.value())))
        else:
            qDebug('rpc call error: %s,%s' % (rr.error().name(), rr.error().message()))

        ### TODO send message faild

        return

    def sendWXDiscusChatMessageToWX(self, groupchat, mcc):

        from_username = groupchat.FromUser.UserName
        to_username = groupchat.ToUser.UserName

        args = [to_username, from_username, mcc, 1, 'more', 'even more']
        reply = self.sysiface.call('send_discus_msg', *args)  # 注意把args扩展开

        rr = QDBusReply(reply)
        if rr.isValid():
            qDebug(str(rr.value()) + ',' + str(type(rr.value())))
        else:
            qDebug('rpc call error: %s,%s' % (rr.error().name(), rr.error().message()))

        ### TODO send message faild

        return

    # TODO 修改为调用asyncGetRpc
    def sendWXSessionChatMessageToWX(self, groupchat, mcc):
        def on_dbus_reply(watcher):
            groupchat, mcc = self.asyncWatchers[watcher]

            pendReply = QDBusPendingReply(watcher)
            message = pendReply.reply()
            args = message.arguments()
            qDebug(str(args))

            # #####
            hcc = args[0]  # QByteArray
            strhcc = self.hcc2str(hcc)
            hccjs = json.JSONDecoder().decode(strhcc)
            print('group sig', ':::', strhcc)

            groupchat.group_sig = hccjs['result']['value']

            self.sendWXSessionChatMessageToWX(groupchat, mcc)
            self.asyncWatchers.pop(watcher)
            return

        # get group sig if None
        if groupchat.group_sig is None:
            gid = groupchat.Gid
            tuin = groupchat.FromUser.UserName  # 也有可能是ToUser.UserName
            service_type = groupchat.ServiceType
            pcall = self.sysiface.asyncCall('get_c2cmsg_sig', gid, tuin, service_type, 'a0', 123, 'a1')
            watcher = QDBusPendingCallWatcher(pcall)
            watcher.finished.connect(on_dbus_reply, Qt.QueuedConnection)
            self.asyncWatchers[watcher] = [groupchat, mcc]

        # ##########

        from_username = groupchat.FromUser.UserName
        to_username = groupchat.ToUser.UserName
        group_sig = groupchat.group_sig

        args = [to_username, from_username, mcc, group_sig, 1, 'more', 'even more']
        reply = self.sysiface.call('send_sess_msg', *args)  # 注意把args扩展开

        rr = QDBusReply(reply)
        if rr.isValid():
            qDebug(str(rr.value()) + ',' + str(type(rr.value())))
        else:
            qDebug('rpc call error: %s,%s' % (rr.error().name(), rr.error().message()))

        ### TODO send message faild

        return

    def sendU2UMessageToWX(self, groupchat, mcc):

        from_username = groupchat.FromUser.UserName
        to_username = groupchat.ToUser.UserName

        args = [to_username, from_username, mcc, 1, 'more', 'even more']
        reply = self.sysiface.call('send_buddy_msg', *args)  # 注意把args扩展开

        rr = QDBusReply(reply)
        if rr.isValid():
            qDebug(str(rr.value()) + ',' + str(type(rr.value())))
        else:
            qDebug('rpc call error: %s,%s' % (rr.error().name(), rr.error().message()))

        ### TODO send message faild

        return

    def createWXSession(self):
        if self.txses is not None:
            return

        self.txses = WXSession()

        reply = self.sysiface.call('getselfinfo', 123, 'a1', 456)
        rr = QDBusReply(reply)
        # TODO check reply valid
        qDebug(str(len(rr.value())) + ',' + str(type(rr.value())))
        data64 = rr.value().encode()   # to bytes
        data = QByteArray.fromBase64(data64)
        self.txses.setSelfInfo(data)
        self.saveContent('selfinfo.json', data)

        pcall = self.sysiface.asyncCall('getuserfriends', 'a0', 123, 'a1')
        watcher = QDBusPendingCallWatcher(pcall)
        watcher.finished.connect(self.onGetContactDone, Qt.QueuedConnection)
        self.asyncWatchers[watcher] = 'getuserfriends'

        pcall = self.sysiface.asyncCall('getgroupnamelist', 'a0', 123, 'a1')
        watcher = QDBusPendingCallWatcher(pcall)
        watcher.finished.connect(self.onGetContactDone, Qt.QueuedConnection)
        self.asyncWatchers[watcher] = 'getgroupnamelist'

        pcall = self.sysiface.asyncCall('getdiscuslist', 'a0', 123, 'a1')
        watcher = QDBusPendingCallWatcher(pcall)
        watcher.finished.connect(self.onGetContactDone, Qt.QueuedConnection)
        self.asyncWatchers[watcher] = 'getdiscuslist'

        # pcall = self.sysiface.asyncCall('getonlinebuddies', 'a0', 123, 'a1')
        # watcher = QDBusPendingCallWatcher(pcall)
        # watcher.finished.connect(self.onGetContactDone)
        # self.asyncWatchers[watcher] = 'getgrouponlinebuddies'

        # pcall = self.sysiface.asyncCall('getrecentlist', 'a0', 123, 'a1')
        # watcher = QDBusPendingCallWatcher(pcall)
        # watcher.finished.connect(self.onGetContactDone)
        # self.asyncWatchers[watcher] = 'getrecentlist'

        # reply = self.sysiface.call('getinitdata', 123, 'a1', 456)
        # rr = QDBusReply(reply)
        # # TODO check reply valid

        # qDebug(str(len(rr.value())) + ',' + str(type(rr.value())))
        # data64 = rr.value().encode('utf8')   # to bytes
        # data = QByteArray.fromBase64(data64)
        # self.txses.setInitData(data)
        # self.saveContent('initdata.json', data)

        # reply = self.sysiface.call('getcontact', 123, 'a1', 456)
        # rr = QDBusReply(reply)

        # # TODO check reply valid
        # qDebug(str(len(rr.value())) + ',' + str(type(rr.value())))
        # data64 = rr.value().encode('utf8')   # to bytes
        # data = QByteArray.fromBase64(data64)
        # self.txses.setContact(data)
        # self.saveContent('contact.json', data)


        # reply = self.sysiface.call('getgroups', 123, 'a1', 456)
        # rr = QDBusReply(reply)

        # # TODO check reply valid
        # qDebug(str(len(rr.value())) + ',' + str(type(rr.value())))
        # GroupNames = json.JSONDecoder().decode(rr.value())

        # self.txses.addGroupNames(GroupNames)

        # # QTimer.singleShot(8, self.getBatchContactAll)
        # QTimer.singleShot(8, self.getBatchGroupAll)

        return

    def checkWXLogin(self):
        reply = self.sysiface.call('islogined', 'a0', 123, 'a1')
        qDebug(str(reply))
        rr = QDBusReply(reply)

        if not rr.isValid(): return False
        qDebug(str(rr.value()) + ',' + str(type(rr.value())))
        if rr.value() is False:
            return False

        return True

    def getConnState(self):
        reply = self.sysiface.call('connstate', 'a0', 123, 'a1')
        qDebug(str(reply))
        rr = QDBusReply(reply)
        qDebug(str(rr.value()) + ',' + str(type(rr.value())))

        return rr.value()

    def sendQQNum(self, num):
        reply = self.sysiface.call('inputqqnum', num, 'a0', 123, 'a1')
        qDebug(str(reply))
        rr = QDBusReply(reply)
        qDebug(str(rr.value()) + ',' + str(type(rr.value())))
        return

    def sendPasswordAndVerify(self, password, verify_code):
        reply = self.sysiface.call('inputverify', password, verify_code, 'a0', 123, 'a1')
        qDebug(str(reply))
        rr = QDBusReply(reply)
        qDebug(str(rr.value()) + ',' + str(type(rr.value())))
        return

    def getGroupsFromDBus(self):

        reply = self.sysiface.call('getgroups', 123, 'a1', 456)
        rr = QDBusReply(reply)

        # TODO check reply valid
        qDebug(str(len(rr.value())) + ',' + str(type(rr.value())))
        GroupNames = json.JSONDecoder().decode(rr.value())

        return GroupNames

    def onGetContactDone(self, watcher):
        pendReply = QDBusPendingReply(watcher)
        qDebug(str(watcher))
        qDebug(str(pendReply.isValid()))
        if pendReply.isValid():
            hcc = pendReply.argumentAt(0)
            qDebug(str(type(hcc)))
        else:
            hcc = pendReply.argumentAt(0)
            qDebug(str(len(hcc)))
            qDebug(str(hcc))
            return

        message = pendReply.reply()
        args = message.arguments()
        qDebug(str(args))
        extrainfo = self.asyncWatchers[watcher]
        self.saveContent('dr.'+extrainfo+'.json', args[0])

        ######
        hcc = args[0]  # QByteArray
        strhcc = self.hcc2str(hcc)
        qDebug(strhcc.encode())
        hccjs = json.JSONDecoder().decode(strhcc)
        print(extrainfo, ':::', strhcc)


        if extrainfo == 'getuserfriends':
            self.txses.setUserFriends(hcc)

        if extrainfo == 'getgroupnamelist':
            self.txses.setGroupList(hcc)
            for um in hccjs['result']['gnamelist']:
                gcode = um['code']
                gname = um['name']
                qDebug(b'get group detail...' + str(um).encode())
                pcall = self.sysiface.asyncCall('get_group_detail', gcode, 'a0', 123, 'a1')
                twatcher = QDBusPendingCallWatcher(pcall)
                twatcher.finished.connect(self.onGetGroupOrDiscusDetailDone, Qt.QueuedConnection)
                self.asyncWatchers[twatcher] = 'get_group_detail'
                qDebug(b'get group detail...' + str(um).encode() + str(twatcher).encode())

        if extrainfo == 'getdiscuslist':
            self.txses.setDiscusList(hcc)
            for um in hccjs['result']['dnamelist']:
                did = um['did']
                dname = um['name']
                qDebug(b'get discus detail...' + str(um).encode())
                pcall = self.sysiface.asyncCall('get_discus_detail', did, 'a0', 123, 'a1')
                twatcher = QDBusPendingCallWatcher(pcall)
                twatcher.finished.connect(self.onGetGroupOrDiscusDetailDone, Qt.QueuedConnection)
                self.asyncWatchers[twatcher] = 'get_discus_detail'
                qDebug(b'get discus detail...' + str(um).encode() + str(twatcher).encode())

        self.asyncWatchers.pop(watcher)
        return

    # TODO delay dbus 请求响应合并处理
    def onGetGroupOrDiscusDetailDone(self, watcher):
        pendReply = QDBusPendingReply(watcher)
        qDebug(str(watcher))
        qDebug(str(pendReply.isValid()))
        if pendReply.isValid():
            hcc = pendReply.argumentAt(0)
            qDebug(str(type(hcc)))
        else:
            hcc = pendReply.argumentAt(0)
            qDebug(str(len(hcc)))
            qDebug(str(hcc))
            return

        message = pendReply.reply()
        args = message.arguments()
        qDebug(str(args))
        extrainfo = self.asyncWatchers[watcher]
        self.saveContent('dr.'+extrainfo+'.json', args[0])
        if len(args[0].data()) == 0:
            qDebug('can not get group or discus list.')
            sys.exit()

        ######
        hcc = args[0]  # QByteArray
        strhcc = self.hcc2str(hcc)
        hccjs = json.JSONDecoder().decode(strhcc)
        print(extrainfo, ':::', strhcc)

        if extrainfo == 'get_group_detail':
            qDebug('gooooooooot')
            self.txses.setGroupDetail(hcc)
            pass

        if extrainfo == 'get_discus_detail':
            qDebug('gooooooooot')
            self.txses.setDiscusDetail(hcc)
            pass

        self.asyncWatchers.pop(watcher)
        return

    def getBatchGroupAll(self):
        groups2 = self.getGroupsFromDBus()
        self.txses.addGroupNames(groups2)
        groups = self.txses.getICGroups()
        qDebug(str(groups))

        reqcnt = 0
        arg0 = []
        for grname in groups:
             melem = {'UserName': grname, 'ChatRoomId': ''}
             arg0.append(melem)

        argjs = json.JSONEncoder().encode(arg0)
        pcall = self.sysiface.asyncCall('getbatchcontact', argjs)
        watcher = QDBusPendingCallWatcher(pcall)
        # watcher.finished.connect(self.onGetBatchContactDone)
        watcher.finished.connect(self.onGetBatchGroupDone)
        self.asyncWatchers[watcher] = arg0
        reqcnt += 1

        qDebug('async reqcnt: ' + str(reqcnt))

        return

    # @param message QDBusPengindCallWatcher
    def onGetBatchGroupDone(self, watcher):
        pendReply = QDBusPendingReply(watcher)
        qDebug(str(watcher))
        qDebug(str(pendReply.isValid()))
        if pendReply.isValid():
            hcc = pendReply.argumentAt(0)
            qDebug(str(type(hcc)))
        else:
            hcc = pendReply.argumentAt(0)
            qDebug(str(len(hcc)))
            qDebug(str(hcc))
            return

        message = pendReply.reply()
        args = message.arguments()
        # qDebug(str(len(args)))

        hcc = args[0]  # QByteArray
        strhcc = self.hcc2str(hcc)
        hccjs = json.JSONDecoder().decode(strhcc)

        # print(strhcc)

        memcnt = 0
        for contact in hccjs['ContactList']:
            memcnt += 1
            # print(contact)
            # self.txses.addMember(contact)
            grname = contact['UserName']
            if not QQUser.isGroup(grname): continue

            print('uid=%s,un=%s,nn=%s\n' % (contact['Uin'], contact['UserName'], contact['NickName']))
            self.txses.addGroupUser(grname, contact)
            if grname in self.pendingGroupMessages and len(self.pendingGroupMessages[grname]) > 0:
                while len(self.pendingGroupMessages[grname]) > 0:
                    msgobj = self.pendingGroupMessages[grname].pop()
                    GroupUser = self.txses.getGroupByName(grname)
                    self.dispatchWXGroupChatToTox2(msgobj[0], msgobj[1], GroupUser)

        qDebug('got memcnt: %s/%s' % (memcnt, len(self.txses.ICGroups)))

        ### flow next
        # QTimer.singleShot(12, self.getBatchContactAll)

        return

    def getBatchContactAll(self):

        groups = self.txses.getICGroups()
        qDebug(str(groups))
        reqcnt = 0
        for grname in groups:
            members = self.txses.getGroupMembers(grname)
            arg0 = []
            for member in members:
                melem = {'UserName': member, 'EncryChatRoomId': group.UserName}
                arg0.append(melem)

            cntpertime = 50
            while len(arg0) > 0:
                subarg = arg0[0:cntpertime]
                subargjs = json.JSONEncoder().encode(subarg)
                pcall = self.sysiface.asyncCall('getbatchcontact', subargjs)
                watcher = QDBusPendingCallWatcher(pcall)
                watcher.finished.connect(self.onGetBatchContactDone)
                self.asyncWatchers[watcher] = subarg
                arg0 = arg0[cntpertime:]
                reqcnt += 1
                break
            break

        qDebug('async reqcnt: ' + str(reqcnt))

        return

    # @param message QDBusPengindCallWatcher
    def onGetBatchContactDone(self, watcher):
        pendReply = QDBusPendingReply(watcher)
        qDebug(str(watcher))
        qDebug(str(pendReply.isValid()))
        if pendReply.isValid():
            hcc = pendReply.argumentAt(0)
            qDebug(str(type(hcc)))
        else:
            return

        message = pendReply.reply()
        args = message.arguments()
        # qDebug(str(len(args)))

        hcc = args[0]  # QByteArray
        strhcc = self.hcc2str(hcc)
        hccjs = json.JSONDecoder().decode(strhcc)

        # qDebug(str(self.txses.getGroups()))
        print(strhcc)

        memcnt = 0
        for contact in hccjs['ContactList']:
            memcnt += 1
            # print(contact)
            self.txses.addMember(contact)

        qDebug('got memcnt: %s/%s' % (memcnt, len(self.txses.ICUsers)))
        return

    def onGetFriendInfoDone(self, watcher):
        pendReply = QDBusPendingReply(watcher)
        qDebug(str(watcher))
        qDebug(str(pendReply.isValid()))
        if pendReply.isValid():
            hcc = pendReply.argumentAt(0)
            qDebug(str(type(hcc)))
        else:
            hcc = pendReply.argumentAt(0)
            qDebug(str(len(hcc)))
            qDebug(str(hcc))
            return

        message = pendReply.reply()
        args = message.arguments()
        qDebug(str(args))
        msg, fmtcc = self.asyncWatchers[watcher]

        ######
        hcc = args[0]  # QByteArray
        strhcc = self.hcc2str(hcc)
        hccjs = json.JSONDecoder().decode(strhcc)
        print(':::', strhcc)

        self.txses.addFriendInfo(hcc)
        if msg.FromUser is None:
            msg.FromUser = self.txses.getUserByName(msg.FromUserName)
        elif msg.ToUser is None:
            msg.ToUser = self.txses.getUserByName(msg.ToUserName)
        else:
            pass

        assert(msg.FromUser is not None)
        assert(msg.ToUser is not None)

        self.dispatchQQSessChatToTox(msg, fmtcc)

        self.asyncWatchers.pop(watcher)
        return

    # @param cb(data)
    def getMsgImgCallback(self, msg, imgcb=None):
        # 还有可能超时，dbus默认timeout=25，而实现有可能达到45秒。WTF!!!
        args = [msg.offpic, msg.FromUserName]
        offpic_file_path = msg.offpic.replace('/', '%2F')
        args = [offpic_file_path, msg.FromUserName]
        self.asyncGetRpc('get_msg_img', args, imgcb)
        return

    # @param cb(data)
    def getMsgFileCallback(self, msg, imgcb=None):
        # 还有可能超时，dbus默认timeout=25，而实现有可能达到45秒。WTF!!!
        # TODO, msg.FileName maybe need urlencoded
        args = [msg.MsgId, msg.FileName, msg.ToUserName]
        self.asyncGetRpc('get_msg_file', args, imgcb)
        return


# hot fix
g_w2t = None


def on_app_about_close():
    qDebug('hereee')
    global g_w2t

    g_w2t.peerRelay.disconnectIt()
    return


def main():
    app = QCoreApplication(sys.argv)
    import wxagent.qtutil as qtutil
    qtutil.pyctrl()

    w2t = WX2Tox()

    global g_w2t
    g_w2t = w2t
    app.aboutToQuit.connect(on_app_about_close)

    app.exec_()
    return


if __name__ == '__main__': main()
