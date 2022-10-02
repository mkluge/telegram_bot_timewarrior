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
from doctest import OutputChecker
from enum import Enum
from os import chdir
from os.path import isfile
from subprocess import PIPE, Popen
from typing import Tuple, Union

import telepot
import telepot.api
from telepot.loop import MessageLoop
from telepot.namedtuple import (InlineKeyboardButton, InlineKeyboardMarkup,
                                KeyboardButton, ReplyKeyboardMarkup)

OWN_COMMANDS = {
    "j": "join the last two items",
    "cj": "continue and join the last two",
    "ls": "list commands",
    "?": "list commands",
}

ON_LABEL = "🟢"
OFF_LABEL = "🔴"


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
        cmd_proc = Popen(
            ["/bin/bash", "-c", self.config["get_timew_commands"]],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
        )
        output, _ = cmd_proc.communicate()
        self.timew_commands = str(output.decode("utf8")).split("\n")
        self.bot = telepot.Bot(self.config["bot_id"])

    @staticmethod
    def iterButtons(buttons: list):
        result = []
        for button in buttons:
            if isinstance(button, list):
                result.append(TimeWarriorBot.iterButtons(button))
            else:
                result.append(InlineKeyboardButton(text=button, callback_data=button))
        return result

    @staticmethod
    def makeKeyboard(buttons: list):
        kbd = TimeWarriorBot.iterButtons(buttons)
        return InlineKeyboardMarkup(inline_keyboard=kbd)

    def call_timew(self, cmds):
        """calls a timewarrior command

        Args:
            cmds (array): timewarrior arguments

        Returns:
            array: output produced by the command, one element per line
        """
        proc = Popen(
            [self.config["timew_path"]] + cmds, stdin=PIPE, stdout=PIPE, stderr=PIPE
        )
        output, err = proc.communicate()
        if len(output) > 0:
            return output.decode("utf8")
        return err.decode("utf8")

    def getTimewarriorStatus(self) -> Tuple[str, Union[str, None], Union[str, None]]:
        """gets the current type of work and
        the topic
        """
        wtype: str = None
        task: str = None
        output = self.call_timew([]).split("\n")
        # we only need the first line, if there are many
        if isinstance(output, list):
            output = output[0]
        # now we only have one (the first) line
        words = output.split(" ")
        # if the first word is Tracking, then somthing
        # is going on
        if words[0] == "Tracking":
            # find type
            for word in words[1:]:
                if word in self.config["types"]:
                    wtype = word
                    break
            # find task
            for word in words[1:]:
                if word in self.config["tasks"]:
                    task = word
                    break
        return (output, wtype, task)

    @staticmethod
    def gen_time_keyboard():
        """generates an inline keyboard with the current time
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
            tw_time = now - datetime.timedelta(minutes=num_5min * 5)
            timestr = tw_time.strftime("%H:%M")
            buttons.append(timestr)
        return buttons

    def setTaskType(self, task: Union[str, None], type: Union[str, None]) -> None:
        _, ctype, ctask = self.getTimewarriorStatus()
        new_type = type if type else ctype
        new_task = task if task else ctask
        self.call_timew(["start", new_task, new_type])

    def cmdToOutput(self, text) -> Tuple[str, InlineKeyboardMarkup]:
        words = text.split(" ")
        cmd = words[0].lower()
        output = ""

        if cmd == "start":
            if len(words) == 1:
                self.current_command = DeepCommands.START
                kbd = TimeWarriorBot.makeKeyboard([self.gen_time_keyboard()])
                return ("Welcome", kbd)
            else:
                output = self.call_timew(
                    [
                        "start",
                        self.config["default_task"],
                        self.config["default_type"],
                        words[1],
                    ]
                )
                self.current_command = DeepCommands.NONE
                return self.getStatus()
        if cmd == "stop":
            if len(words) == 1:
                self.current_command = DeepCommands.STOP
                kbd = TimeWarriorBot.makeKeyboard([self.gen_time_keyboard()])
                return ("Bye", kbd)
            else:
                output = self.call_timew(["stop", words[1]])
                self.current_command = DeepCommands.NONE
                return self.getStatus()
        if self.time_pattern.match(cmd):
            output = ""
            if self.current_command == DeepCommands.START:
                output = self.call_timew(
                    [
                        "start",
                        self.config["default_task"],
                        self.config["default_type"],
                        cmd,
                    ]
                )
            elif self.current_command == DeepCommands.STOP:
                output = self.call_timew(["stop", cmd])
            self.current_command = DeepCommands.NONE
            return self.getStatus()
        # check whether we got a work type or a task
        if words[0] in self.config["tasks"]:
            self.setTaskType(words[0], None)
        if words[0] in self.config["types"]:
            self.setTaskType(None, words[0])

        status_output, keyboard = self.getStatus()
        if cmd == "week":
            output = self.call_timew(["week"])
        if cmd == "cancel":
            output = self.call_timew(["cancel"])
        if cmd == "status":
            output = self.call_timew(["summary", ":ids"])
        if isinstance(output, list):
            txt = "\n".join(output)
        else:
            txt = output
        if not txt:
            txt = status_output
        return (txt, keyboard)

    def callbackQuery(self, msg):
        query_id, from_id, cmd = telepot.glance(msg, flavor="callback_query")
        if msg["from"]["id"] != self.config["user_id"]:
            return
        answer, keyboard = self.cmdToOutput(cmd)
        self.bot.answerCallbackQuery(query_id, "OK")
        self.sendStatus(msg["message"]["chat"]["id"], answer, keyboard)

    def chat(self, msg):
        """called if user sends a message to the chat
        Args:
            msg (): the chat message
        """
        _, _, chat_id = telepot.glance(msg)
        # check for the correct user id
        if msg["from"]["id"] != self.config["user_id"]:
            return

        text = msg["text"]
        output, keyboard = self.cmdToOutput(text)
        self.sendStatus(chat_id, output, keyboard)

    def getStatus(self) -> Tuple[str, InlineKeyboardMarkup]:
        # if not, check, what time warrior has as current status
        output, wtype, task = self.getTimewarriorStatus()
        # figure out which keys to send
        # the logic is as follows:
        # if we want a time, only send the time buttons
        # !this is already done by the code above
        # if time is tracked, send stop, status, week
        #    and the work types and topics and show the
        #    active ones#
        if wtype or task:
            now_wtypes = [
                ON_LABEL + t if wtype == t else t for t in self.config["types"]
            ]
            now_tasks = [ON_LABEL + t if task == t else t for t in self.config["tasks"]]
            keyboard = TimeWarriorBot.makeKeyboard(
                [["Stop", "Status", "Week"], now_wtypes, now_tasks]
            )
        # if time is not tracked, show only start, status,
        #    and week
        else:
            keyboard = TimeWarriorBot.makeKeyboard([["Start", "Status", "Week"]])
        return (output, keyboard)

    def sendStatus(self, chat_id, text, keyboard):
        # if we get a keyboard and a text,
        # send them
        self.bot.sendMessage(
            chat_id,
            "```\n" + text + "\n```",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )


# main program
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=str, action="store", default="config.json", dest="config_file"
    )
    args = parser.parse_args()

    if not isfile(args.config_file):
        print(f"config file {args.config_file} not present")
        sys.exit(1)
    with open(args.config_file, "r") as f:
        cfg = json.load(f)
        twbot = TimeWarriorBot(cfg)
        MessageLoop(
            twbot.bot,
            {
                "chat": twbot.chat,
                "callback_query": twbot.callbackQuery,
            },
        ).run_as_thread()
        print("I am listening ...")

        while 1:
            time.sleep(10)
