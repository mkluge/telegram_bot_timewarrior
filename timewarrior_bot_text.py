#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    Telegram bot frontend for timewarrior

    Michael Kluge
    vollseil@gmail.com

"""

from distutils.command.config import config
from enum import Enum
from os import chdir
import time
import sys
import datetime
import json
import re
import argparse
from os.path import isfile
from subprocess import Popen, PIPE
import telepot
import telepot.api
from telepot.loop import MessageLoop
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton

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
     KeyboardButton(text='W')]],
    resize_keyboard=True,
)

ON_LABEL='🟢'
OFF_LABEL='🔴'

class DeepCommands(Enum):
    NONE = 0
    START = 1
    STOP = 2


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


def gen_time_keyboard():
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
    return ReplyKeyboardMarkup(keyboard=[buttons],
                               resize_keyboard=True)


def handle(msg):
    """ called if user sends a message to the chat

    Args:
        msg (): the chat message
    """
    _, _, chat_id = telepot.glance(msg)

    # check for the correct user id
    if msg['from']['id'] != CONFIG["user_id"]:
        return

    text = msg['text']
    words = text.split(" ")
    cmd = words[0].lower()
    output = ""
    global current_command

    if cmd == "start":
        if len(words) == 1:
            current_command = DeepCommands.START
            kbd = gen_time_keyboard()
            BOT.sendMessage(chat_id, 'Welcome', reply_markup=kbd)
            return
        else:
            output = call_timew(['start', CONFIG["default_task"], words[1]])
            current_command = DeepCommands.NONE
    if cmd == "stop":
        if len(words) == 1:
            current_command = DeepCommands.STOP
            kbd = gen_time_keyboard()
            BOT.sendMessage(chat_id, 'Bye', reply_markup=kbd)
            return
        else:
            output = call_timew(['stop', words[1]])
            current_command = DeepCommands.NONE
    if time_pattern.match(cmd):
        if current_command == DeepCommands.START:
            output = call_timew(['start', CONFIG["default_task"], cmd])
            current_command = DeepCommands.NONE
        elif current_command == DeepCommands.STOP:
            output = call_timew(['stop', CONFIG["default_task"], cmd])
            current_command = DeepCommands.NONE
        else:
            output = "did not get that"
    if cmd == "w":
        output = call_timew(['week'])
    if cmd == "year":
        now = datetime.datetime.now()
        timestr = now.strftime("%Y-01-01")
        output = call_timew(['week', timestr, 'to', 'today'])
    if cmd == "cancel":
        output = call_timew(['cancel'])
    if cmd == "status":
        output = call_timew(['summary', ':ids'])
    if isinstance(output, list):
        txt = "\n".join(output)
    else:
        txt = output
    if not txt:
        txt = "Nope"

    txt = "```\n"+txt+"\n```"
    BOT.sendMessage(chat_id, txt, parse_mode="Markdown",
                    reply_markup=STANDARD_KEYBOARD)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--config', type=str, action='store', default='config.json', dest='config_file')
args = parser.parse_args()

if not isfile(args.config_file):
    print(f'config file {args.config_file} not present')
    sys.exit(1)
with open(args.config_file, 'r') as f:
    CONFIG = json.load(f)


# main program
# get a list of commands known to timew
CMD_PROC = Popen(["/bin/bash", "-c", CONFIG["get_timew_commands"]],
                 stdin=PIPE, stdout=PIPE, stderr=PIPE)
OUTPUT, _ = CMD_PROC.communicate()
TIMEW_COMMANDS = str(OUTPUT.decode('utf8')).split('\n')
current_command = DeepCommands.NONE
time_pattern = re.compile("^[0-9][0-9]:[0-9][0-9]$")

BOT = telepot.Bot(CONFIG["bot_id"])
MessageLoop(BOT, {'chat': handle}).run_as_thread()
print('I am listening ...')

while 1:
    time.sleep(10)
