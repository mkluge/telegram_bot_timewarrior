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
from enum import Enum
from os.path import isfile
from subprocess import PIPE, Popen
from typing import Tuple, Union

import telepot.api
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardButton, InlineKeyboardMarkup

OWN_COMMANDS = {
    "j": "join the last two items",
    "cj": "continue and join the last two",
    "ls": "list commands",
    "?": "list commands",
}

ON_LABEL = "🟢"
OFF_LABEL = "🔴"


class DeepCommands(Enum):
    """constants for the internal state"""

    NONE = 0
    START = 1
    STOP = 2


class TimeWarriorBot:
    """telegram bot that talks to a local timewarrior instance"""

    config = {}
    bot = {}
    current_command = DeepCommands.NONE
    time_pattern = re.compile("^[0-9][0-9]:[0-9][0-9]$")
    timew_commands = []

    def __init__(self, config) -> None:
        self.config = config
        # get a list of commands known to timew
        with Popen(
            ["/bin/bash", "-c", self.config["get_timew_commands"]],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
        ) as cmd_proc:
            output, _ = cmd_proc.communicate()
            self.timew_commands = str(output.decode("utf8")).split("\n")
            self.bot = telepot.Bot(self.config["bot_id"])

    @staticmethod
    def iter_buttons(buttons: list):
        """create a list of button from a list of text"""
        result = []
        for button in buttons:
            if isinstance(button, list):
                result.append(TimeWarriorBot.iter_buttons(button))
            else:
                result.append(InlineKeyboardButton(text=button, callback_data=button))
        return result

    @staticmethod
    def make_keyboard(buttons: list) -> InlineKeyboardMarkup:
        """generates a keyboard from a list of lists with buttons

        Args:
            buttons (list): list of lists of buttons

        Returns:
            InlineKeyboardMarkup: an inline keyboard
        """
        kbd = TimeWarriorBot.iter_buttons(buttons)
        return InlineKeyboardMarkup(inline_keyboard=kbd)

    def call_timew(self, cmds):
        """calls a timewarrior command

        Args:
            cmds (array): timewarrior arguments

        Returns:
            array: output produced by the command, one element per line
        """
        with Popen(
            [self.config["timew_path"]] + cmds, stdin=PIPE, stdout=PIPE, stderr=PIPE
        ) as proc:
            output, err = proc.communicate()
            if len(output) > 0:
                return output.decode("utf8")
            return err.decode("utf8")

    def get_timewarrior_status(self) -> Tuple[str, Union[str, None], Union[str, None]]:
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

    def set_task_type(self, task: Union[str, None], wtype: Union[str, None]) -> None:
        """sets the current work type or/and the current task

        Args:
            task (Union[str, None]): new task, can be None
            wtype (Union[str, None]): new work type, can be None
        """
        _, ctype, ctask = self.get_timewarrior_status()
        new_type = wtype if wtype else ctype
        new_task = task if task else ctask
        self.call_timew(["start", new_task, new_type])

    # pylint: disable=too-many-branches
    def cmd_to_output(self, text: str) -> Tuple[str, InlineKeyboardMarkup]:
        """runs a command, collects the output and generates a new inline keyboard

        Args:
            text (str): the line send from the client

        Returns:
            Tuple[str, InlineKeyboardMarkup]: the output from timewarrior and
                                              a new inline keyboard
        """
        words = text.split(" ")
        cmd = words[0].lower()
        output = ""

        if cmd == "start":
            if len(words) == 1:
                self.current_command = DeepCommands.START
                kbd = TimeWarriorBot.make_keyboard([self.gen_time_keyboard()])
                return ("Welcome", kbd)
            output = self.call_timew(
                [
                    "start",
                    self.config["default_task"],
                    self.config["default_type"],
                    words[1],
                ]
            )
            self.current_command = DeepCommands.NONE
            return self.get_status()
        if cmd == "stop":
            if len(words) == 1:
                self.current_command = DeepCommands.STOP
                kbd = TimeWarriorBot.make_keyboard([self.gen_time_keyboard()])
                return ("Bye", kbd)
            output = self.call_timew(["stop", words[1]])
            self.current_command = DeepCommands.NONE
            return self.get_status()
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
            return self.get_status()
        # check whether we got a work type or a task
        if words[0] in self.config["tasks"]:
            self.set_task_type(words[0], None)
        if words[0] in self.config["types"]:
            self.set_task_type(None, words[0])

        status_output, keyboard = self.get_status()
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

    def callback_query(self, msg: str) -> None:
        """called with data from an inline button if user
            presses one of them

        Args:
            msg (str): the data associated with the button
        """
        query_id, _, cmd = telepot.glance(msg, flavor="callback_query")
        if msg["from"]["id"] != self.config["user_id"]:
            return
        answer, keyboard = self.cmd_to_output(cmd)
        self.bot.answerCallbackQuery(query_id, "OK")
        self.send_status(msg["message"]["chat"]["id"], answer, keyboard)

    def chat(self, msg: str) -> None:
        """called if user sends a message to the chat
        Args:
            msg (): the chat message
        """
        _, _, chat_id, _, _ = telepot.glance(msg)
        # check for the correct user id
        if msg["from"]["id"] != self.config["user_id"]:
            return

        text = msg["text"]
        output, keyboard = self.cmd_to_output(text)
        self.send_status(chat_id, output, keyboard)

    def get_status(self) -> Tuple[str, InlineKeyboardMarkup]:
        """gets the current timewarrior task and status

        Returns:
            Tuple[str, InlineKeyboardMarkup]: returns the status and a
                                              status dependent inline keyboard
        """
        # if not, check, what time warrior has as current status
        output, wtype, task = self.get_timewarrior_status()
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
            keyboard = TimeWarriorBot.make_keyboard(
                [["Stop", "Status", "Week"], now_wtypes, now_tasks]
            )
        # if time is not tracked, show only start, status,
        #    and week
        else:
            keyboard = TimeWarriorBot.make_keyboard([["Start", "Status", "Week"]])
        return (output, keyboard)

    def send_status(
        self, chat_id: str, text: str, keyboard: InlineKeyboardMarkup
    ) -> None:
        """sends a message and some options to the client how to proceed

        Args:
            chat_id (str): the current chat id
            text (str): the text for the message
            keyboard (InlineKeyboardMarkup): the new feedback options for the user
        """
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
    with open(args.config_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)
        twbot = TimeWarriorBot(cfg)
        MessageLoop(
            twbot.bot,
            {
                "chat": twbot.chat,
                "callback_query": twbot.callback_query,
            },
        ).run_as_thread()
        print("I am listening ...")

        while 1:
            time.sleep(10)
