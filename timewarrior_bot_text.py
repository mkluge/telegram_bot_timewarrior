#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    Telegram bot frontend for timewarrior

    Michael Kluge
    vollseil@gmail.com

"""

import time
import sys
import datetime
import json
from os.path import isfile
from subprocess import Popen, PIPE
import telepot
import telepot.api
from telepot.loop import MessageLoop
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton

CONFIG_FILE_NAME = 'config.json'

OWN_COMMANDS = {
    "j": "join the last two items",
    "cj": "continue and join the last two",
    "ls": "list commands",
    "?": "list commands"
}

STANDARD_KEYBOARD = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Start'),
     KeyboardButton(text='Stop'),
     KeyboardButton(text='Cancel'),
     KeyboardButton(text='Status'),
     KeyboardButton(text='W')],
])


def call_timew(cmds):
    """ calls a timewarrior command

    Args:
        cmds (array): timewarrior arguments

    Returns:
        array: output produced by the command, one element per line
    """
    proc = Popen([CONFIG["timew_path"]]+cmds,
                 stdin=PIPE, stdout=PIPE, stderr=PIPE)
    output, err = proc.communicate()
    if len(output) > 0:
        return output.decode('utf8')
    return err.decode('utf8')


def gen_time_keyboard(prefix):
    """ generates an inline keyboard with the current time
        and 3x5 minutes back in time

    Args:
        prefix (string): a prefix that the callback can use to
           identify from which keyboard the message was sent

    Returns:
        InlineKeyboardMarkup: the inline keyboard
    """
    buttons = []
    now = datetime.datetime.now()
    for num_5min in range(0, 4):
        tw_time = now - datetime.timedelta(minutes=num_5min*5)
        timestr = tw_time.strftime("%H:%M")
        buttons.append(KeyboardButton(text=timestr))
    return ReplyKeyboardMarkup(keyboard=[buttons])


def on_virtual_keyboard(msg):
    """ called when a key on the virtual keyboard is pressed

    Args:
        msg (): Message attached with keypress
    """
    _, from_id, query_data = telepot.glance(
        msg, flavor='callback_query')
    if query_data == "start":
        BOT.sendMessage(from_id, "Let's go",
                        reply_markup=gen_time_keyboard("start"))
        return
    if query_data == "stop":
        BOT.sendMessage(from_id, "Ende",
                        reply_markup=gen_time_keyboard("stop"))
        return
    output = "wrong command"
    if query_data == "week":
        output = call_timew(['week'])
    if query_data == "year":
        now = datetime.datetime.now()
        timestr = now.strftime("%Y-01-01")
        output = call_timew(['week', timestr, 'to', 'today'])
    if query_data == "cancel":
        output = call_timew(['cancel'])
    if query_data.startswith("start+"):
        time_str = query_data.split("+")[1]
        output = call_timew(['start', CONFIG["default_task"], time_str])
    if query_data.startswith("stop+"):
        time_str = query_data.split("+")[1]
        output = call_timew(['stop', time_str])
    if query_data == "status":
        output = call_timew(['summary', ':ids'])
    if isinstance(output, list):
        txt = "\n".join(output)
    else:
        txt = output
    txt = "```\n"+txt+"\n```"
    BOT.sendMessage(from_id, txt, parse_mode="Markdown",
                    reply_markup=STANDARD_KEYBOARD)


def handle(msg):
    """ called if user sends a message to the chat

    Args:
        msg (): the chat message
    """
    _, _, chat_id = telepot.glance(msg)
    text = msg['text']

    # check for the correct user id
    if msg['from']['id'] != CONFIG["user_id"]:
        return

    words = text.split(" ")
    cmd = words[0].lower()
    output = []
    # on my own commands, just do this ...
    if cmd in OWN_COMMANDS:
        # list of commands
        if cmd in ["ls", "?"]:
            for key in sorted(OWN_COMMANDS.keys()):
                output.append("%s: %s" % (key, OWN_COMMANDS[key]))
                # join the last two
        if cmd == "j":
            output = call_timew(['join', '@1', '@2'])
        # continue and join the last two
        if cmd == "cj":
            output = call_timew(['continue'])
            output = output + call_timew(['join', '@1', '@2'])
    else:
        # if no known command is given, use "start"
        if not cmd in TIMEW_COMMANDS:
            cmd = "start"
            words = words[0:]
        else:
            words = words[1:]
        real_words = []
        for word in words:
            if word in CONFIG["task_shortcuts"]:
                real_words.append(CONFIG["task_shortcuts"][word])
            else:
                real_words.append(word)
        # if cmd is start, check that at least one of the known
        # activity types is used
        if cmd == "start":
            # wenn kein Wort oder Wort mit Zahl
            # anfängt, ist es eine Zeitangabe
            # dann muss noch der Standard davor
            if not real_words:
                real_words = [CONFIG["default_task"]]
            if real_words[0][0].isdigit():
                real_words.insert(0, CONFIG["default_task"])
        cmds = [cmd]+real_words
        output = call_timew(cmds)
    if isinstance(output, list):
        txt = "\n".join(output)
    else:
        txt = output
    txt = "```\n"+txt+"\n```"
    BOT.sendMessage(chat_id, txt, parse_mode="Markdown",
                    reply_markup=STANDARD_KEYBOARD)


if not isfile(CONFIG_FILE_NAME):
    print("config file "+CONFIG_FILE_NAME+" not present")
    sys.exit(1)
with open(CONFIG_FILE_NAME, 'r') as f:
    CONFIG = json.load(f)


# main program
# get a list of commands known to timew
CMD_PROC = Popen(["/bin/bash", "-c", CONFIG["get_timew_commands"]],
                 stdin=PIPE, stdout=PIPE, stderr=PIPE)
OUTPUT, _ = CMD_PROC.communicate()
TIMEW_COMMANDS = str(OUTPUT.decode('utf8')).split('\n')

BOT = telepot.Bot(CONFIG["bot_id"])
MessageLoop(BOT, {'chat': handle,
                  'callback_query': on_virtual_keyboard}).run_as_thread()
print('I am listening ...')

while 1:
    time.sleep(10)
