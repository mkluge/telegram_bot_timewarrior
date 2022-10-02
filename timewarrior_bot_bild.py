#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import sys
import random
import datetime
import telepot
import urllib3
import telepot.api
import telepot
import json
from PIL import Image, ImageDraw, ImageFont
from subprocess import Popen, PIPE

shortcuts_data_filename = "/root/timewarrior_shortcuts.json"
own_commands = {
    "j": "join the last two items",
    "ls": "list all shortcuts",
    "cj": "continue and join the last two",
    "as": "add a shortcut as <short> <long>",
    "ds": "delete shortcut",
    "lc": "list commands",
    "report": "generate time report",
    "?": "list commands",
}
bot_id = "300537435:AAHGk6CEBwuLAj1j66YVmNML8--rTEd_Elc"
vollseil_user_id = 247027787
get_timew_commands = "timew help | grep Additional -B1000 | grep timew | grep -v Usage | awk '{print $2}'"
# myproxy_url = 'http://172.22.1.3:3128/'

persons = ["NK", "Neda", "Siavash"]
activities = [
    "Administration",
    "Beratung",
    "Ausschreibung",
    "Dokumentation",
    "Entwicklung",
    "Feier",
    "Forschung",
    "Management",
    "Meeting",
    "Ticket-Bearbeitung",
    "Orga-Chef",
    "Organisation",
    "Ortswechsel",
    "Paper",
    "Präsentation",
    "Review",
    "Schulung",
    "Selbst-Orga",
    "Telefonat",
    "Telefonkonferenz",
    "Videokonferenz",
]
special_report_tags = ["Dienstreise", "Urlaub"]


def send_image_from_text(bot, chat_id, lines):
    line_h = 20
    letter_w = 10
    h = len(lines) * line_h
    w = max(map(len, lines)) * letter_w
    img = Image.new("RGB", (w, h), color=(40, 40, 40))
    fnt = ImageFont.truetype("/root/unir.ttf", 15)
    d = ImageDraw.Draw(img)
    line_n = 0
    for line in lines:
        line_s = 5 + (line_h * line_n)
        line_n = line_n + 1
        d.text((10, line_s), line, font=fnt, fill=(0, 255, 0))
    img.save("output.png")
    fp = open("output.png", "rb")
    bot.sendPhoto(chat_id, ("output", fp), caption="output.png")


def load_shortcuts():
    global shortcuts_data_filename
    global shortcuts
    with open(shortcuts_data_filename, "r") as fp:
        shortcuts = json.load(fp)


def store_shortcuts():
    global shortcuts_data_filename
    global shortcuts
    with open(shortcuts_data_filename, "w") as fp:
        json.dump(shortcuts, fp, sort_keys=True, indent=4, separators=(",", ": "))


def call_timew(cmds):
    p = Popen(["/usr/local/bin/timew"] + cmds, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    output, err = p.communicate()
    if len(output) > 0:
        return output.decode("utf8")
    else:
        return err.decode("utf8")


def get_complete_tag_list():
    result = []
    tmp = call_timew(["tags"])
    tmp = str(tmp).split("\n")
    for line in tmp:
        if "-" in line:
            result.append(line.split(" ")[0])
    return result[1:]


def report_for_activity_list(activity_list, timelen):
    sum_secs = 0
    result = {}
    ltime = {}
    for activity in activity_list:
        tmp = call_timew(["summary", timelen, "before", "now", activity])
        tmp = str(tmp).split("\n")
        # get the last nonempty line
        for line in reversed(tmp):
            if len(line) > 0:
                tmp = line.strip()
                break
        if "No filtered data" in tmp:
            continue
        ltime[activity] = tmp
        parts = tmp.split(":")
        secs = 0
        if len(parts) == 3:
            secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            secs = int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 1:
            secs = int(parts[0])
        result[activity] = secs
        sum_secs = sum_secs + secs
    for activity in result:
        result[activity] = (
            str(int(100 * result[activity] / sum_secs)) + "%," + str(ltime[activity])
        )
    output = []
    string = ""
    for key in result.keys():
        string = string + ("%s(%s) " % (key, result[key]))
    return string


def handle(msg):
    global vollseil_user_id
    global own_commands
    global timew_commands
    global shortcuts
    chat_id = msg["chat"]["id"]
    text = msg["text"]

    if msg["from"]["id"] != vollseil_user_id:
        return

    words = text.split(" ")
    cmd = words[0].lower()
    output = []
    # on my own commands, just do this ...
    if cmd in own_commands:
        # list of commands
        if cmd == "lc" or cmd == "?":
            for key in sorted(own_commands.keys()):
                output.append("%s: %s" % (key, own_commands[key]))
        # add a shortcut
        if cmd == "as":
            shortcuts[words[1]] = words[2]
            store_shortcuts()
        # remove a shortcut
        if cmd == "ds":
            shortcuts.pop(words[1], None)
            store_shortcuts()
        # list of shortcuts
        if cmd == "ls":
            for value in sorted(shortcuts.values()):
                key = [k for k, v in shortcuts.items() if v == value]
                output.append("%s => %s" % (value, str(key)))
        # just join the last two
        if cmd == "j":
            output = call_timew(["join", "@1", "@2"])
        # continue and join the last two
        if cmd == "cj":
            output = call_timew(["continue"])
            output = output + call_timew(["join", "@1", "@2"])
        if cmd == "report":
            result = {}
            sum_secs = 0
            timelen = "4w"
            if len(words) > 1:
                timelen = words[1]
            # one report for all activities
            activity_report = report_for_activity_list(activities, timelen)
            output.append(activity_report)
            # one report for all projects
            # projects means: all tags, without activites, without special tags,
            # without persons
            taglist = get_complete_tag_list()
            projects = set(taglist) - set(special_report_tags)
            projects = projects - set(activities)
            projects = projects - set(persons)
            project_report = report_for_activity_list(list(projects), timelen)
            output.append(project_report)
            # one report for special stuff
            special_report = report_for_activity_list(special_report_tags, timelen)
            output.append(special_report)
    else:
        # if no known command is given, use "start"
        if not cmd in timew_commands:
            cmd = "start"
            words = words[0:]
        else:
            words = words[1:]
        real_words = []
        for word in words:
            if word in shortcuts:
                real_words.append(shortcuts[word])
            else:
                real_words.append(word)
        # if cmd is start, check that at least one of the known
        # activity types is used
        if cmd == "start":
            found = False
            for word in real_words:
                if word in activities:
                    found = True
                    break
            if found == False:
                real_words = ["Management"]
            # bot.sendMessage(chat_id, "need one of the known activities")
            # bot.sendMessage(chat_id, "need one of the known activities")
            # bot.sendMessage(chat_id, str(activities))
            # return
        cmds = [cmd] + real_words
        output = call_timew(cmds)
    if type(output) != list:
        output = output.split("\n")
        send_image_from_text(bot, chat_id, output)
    else:
        send_image_from_text(bot, chat_id, output)


# main program
# get a list of commands known to timew
load_shortcuts()
p = Popen(["/bin/bash", "-c", get_timew_commands], stdin=PIPE, stdout=PIPE, stderr=PIPE)
output, err = p.communicate()
timew_commands = str(output.decode("utf8")).split("\n")
print(timew_commands)

# telepot.api._pools = {'default': urllib3.ProxyManager(proxy_url=myproxy_url, num_pools=3, maxsize=10, retries=False, timeout=30),}
# telepot.api._onetime_pool_spec = (urllib3.ProxyManager, dict(proxy_url=myproxy_url, num_pools=1, maxsize=1, retries=False, timeout=30))

bot = telepot.Bot(bot_id)
bot.message_loop(handle)
print("I am listening ...")

while 1:
    time.sleep(10)
