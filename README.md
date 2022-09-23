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

For automated deployment add a file to /etc/sudoers.d/ and put content like
```
timewarrior ALL = NOPASSWD: /usr/bin/systemctl restart timewarrior
```
into it (assuming 'timewarrior' is the uid of the user ...)

## Automatic deployment during development

add a in the git repo a "hooks/post-receive" file and put into it:
```
git --work-tree=/var/www/deployed_project --git-dir=/path/to/bare_project.git checkout -f
systemctl restart timewarrior
```

- chmod +x hooks/post-receive
- add ssh access to the server where you want to run the service
- add the remote to your local git repo
  - git remote add deployment 'timearrior@your-server:/path/to/bare_project.git'
  - git push --set-upstream deployment master



## Usage

You can send the bot all [timewarrior commands](https://timewarrior.net/docs/). The bot provides a virtual keyboard for some commands. The start and the stop buttons record the time with the default activity. Send the bot "?" to get a list of all commands.

