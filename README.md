# good-music-bot
a not awful discord music bot

to installed required dependencies run:
```
python -m venv .venv
source .venv/bin/activate
pip install .
```

### API docs
https://discordpy.readthedocs.io/en/latest/api.html#

https://wavelink.readthedocs.io/en/latest/


--------------------------------------------------------

## linux dependencies ##

* python3.11
* python3-devel (or equiv compile options?)
* libffi-dev
* git (for automatic updates)
* tmux (for interactable autostart)
* Java (JDK) 17
* Lavalink (included)


--------------------------------------------------------

## .env file ##

bot token and Lavalink password must be stored in a .env file in the top level directory.

Example format:

TOKEN = "NDUMTIxQDQ1MzgzMTc1GqucK2Zy80vW7FjoXWaXzNzQ0L9h6HPLWMY9vrYCq8eX39BiZYo"
Lavalink_Password = "youshallnotpass"
