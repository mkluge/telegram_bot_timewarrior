# Telegram Bot for Timewarrior

I like to use [timewarrior](https://timewarrior.net/) for tracking my time. I also like to use my phone for starting and stopping the clock.

## Installation and Configuration

First, install timewarrior on the machine where the bot will run later. You need a telegram account and a bot. Then you nee to create a config file (use the template provided) and run the bot as a python service. You will need to install the telpot python library which can be done with ``pip3 install telepot``.

### Install timewarrior

Got to the [webpage](https://timewarrior.net/) and follow the instructions. If you want, edit and copy the options file (timewarrior.cfg) and put it into it place.

### Get a Telegram account and a bot

Install Telegram. Get your user id by sending a message to @userinfobot in Telegram. Put your user id into the config file.

[Create a telegram bot](https://core.telegram.org/bots). Get the bot HTTP API token and put it into the bot id field in the config file.

### Clone this repo and install the python service

First part is easy. The second looks in my case like this:
```python
linux:~$ cat /etc/systemd/system/timewarrior.service 
[Unit]
# Human readable name of the unit
Description=Timewarrior Telegram Service

[Service]
# Command to execute when the service is started
ExecStart=/usr/bin/python3 /path/to/timewarrior_bot.py

[Install]
WantedBy=default.target

```
Or just run the script with python3.

## Usage

You can send the bot all [timewarrior commands](https://timewarrior.net/docs/). The bot provides a virtual keyboard for some commands. The start and the stop buttons record the time with the default activity. Send the bot "?" to get a list of all commands.

