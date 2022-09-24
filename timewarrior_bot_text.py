#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    Telegram bot frontend for timewarrior

    Michael Kluge
    vollseil@gmail.com

"""

import argparse
import datetime
import json
import re
import sys
import time
from distutils.command.config import config
from enum import Enum
from os import chdir
from os.path import isfile
from subprocess import PIPE, Popen
from typing import Tuple, Union

import telepot
import telepot.api
from telepot.loop import MessageLoop
from telepot.namedtuple import KeyboardButton, ReplyKeyboardMarkup

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

class TimeWarriorBot:

    config = {}
    bot = {}
    current_command = DeepCommands.NONE
    time_pattern = re.compile("^[0-9][0-9]:[0-9][0-9]$")
    timew_commands = []

    def __init__(self, config) -> None:
        self.config = config
        # get a list of commands known to timew
        cmd_proc = Popen(["/bin/bash", "-c", self.config["get_timew_commands"]],
                        stdin=PIPE, stdout=PIPE, stderr=PIPE)
        output, _ = cmd_proc.communicate()
        self.timew_commands = str(output.decode('utf8')).split('\n')
        self.bot = telepot.Bot(self.config["bot_id"])

    def call_timew(self, cmds):
        """ calls a timewarrior command

        Args:
            cmds (array): timewarrior arguments

        Returns:
            array: output produced by the command, one element per line
        """
        proc = Popen([self.config["timew_path"]]+cmds,
                    stdin=PIPE, stdout=PIPE, stderr=PIPE)
        output, err = proc.communicate()
        if len(output) > 0:
            return output.decode('utf8')
        return err.decode('utf8')

    def get_current_status(self) -> Tuple[Union[str,None],Union[str,None]]:
        """ gets the current type of work and
            the topic
        """
        wtype: str = None
        task: str = None
        output = self.call_timew([])
        # we only need the first line, if there are many
        if isinstance( output, list):
            output = output[0]
        # now we only have one (the first) line
        words = output.split(' ')
        # if the first word is Tracking, then somthing
        # is going on
        if words[0] == 'Tracking':
            # find type
            for word in words[1:]:
                if word in self.config['types']:
                    wtype = word
                    break
            # find task  
            for word in words[1:]:
                if word in self.config['tasks']:
                    task = word       
        return (wtype, task)

    @staticmethod
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


    def handle( self, msg):
        """ called if user sends a message to the chat
        Args:
            msg (): the chat message
        """
        _, _, chat_id = telepot.glance(msg)

        # check for the correct user id
        if msg['from']['id'] != self.config["user_id"]:
            return

        text = msg['text']
        words = text.split(" ")
        cmd = words[0].lower()
        output = ''

        if cmd == "start":
            if len(words) == 1:
                self.current_command = DeepCommands.START
                kbd = self.gen_time_keyboard()
                self.bot.sendMessage(chat_id, 'Welcome', reply_markup=kbd)
                return
            else:
                output = self.call_timew(['start', self.config["default_task"], words[1]])
                self.current_command = DeepCommands.NONE
        if cmd == "stop":
            if len(words) == 1:
                self.current_command = DeepCommands.STOP
                kbd = self.gen_time_keyboard()
                self.bot.sendMessage(chat_id, 'Bye', reply_markup=kbd)
                return
            else:
                output = self.call_timew(['stop', words[1]])
                self.current_command = DeepCommands.NONE
        if self.time_pattern.match(cmd):
            if self.current_command == DeepCommands.START:
                output = self.call_timew(['start', self.config["default_task"], cmd])
                self.current_command = DeepCommands.NONE
            elif self.current_command == DeepCommands.STOP:
                output = self.call_timew(['stop', self.config["default_task"], cmd])
                self.current_command = DeepCommands.NONE
            else:
                output = "did not get that"
        if cmd == "w":
            output = self.call_timew(['week'])
        if cmd == "year":
            now = datetime.datetime.now()
            timestr = now.strftime("%Y-01-01")
            output = self.call_timew(['week', timestr, 'to', 'today'])
        if cmd == "cancel":
            output = self.call_timew(['cancel'])
        if cmd == "status":
            output = self.call_timew(['summary', ':ids'])
        if isinstance(output, list):
            txt = "\n".join(output)
        else:
            txt = output
        if not txt:
            txt = "Nope"

        txt = "```\n"+txt+"\n```"
        self.bot.sendMessage(chat_id, txt, parse_mode="Markdown",
                   reply_markup=STANDARD_KEYBOARD)


# main program
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=str, action='store', default='config.json', dest='config_file')
    args = parser.parse_args()

    if not isfile(args.config_file):
        print(f'config file {args.config_file} not present')
        sys.exit(1)
    with open(args.config_file, 'r') as f:
        cfg = json.load(f)
        twbot = TimeWarriorBot(cfg)
        MessageLoop( twbot.bot, {'chat': twbot.handle}).run_as_thread()
        print('I am listening ...')

        while 1:
            time.sleep(10)
