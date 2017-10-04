# steamwhat

A small web application to find out which game you and your friends share on
Steam.

![](https://i.imgur.com/gSLQrhr.gif)

## How to use

You need one or more `steamID64`s, which are also called the "community IDs"
and can be found in your Steam profile URL. If your profile URL is not
yet visible, acticate it via `Steam > Settings > Interface > Display
Steam URL address bar when available`. Then If you happen to know one of your
other Steam IDs you can convert it to the steam64ID format [here](https://steamid.io/lookup/).

## Development

The app is written using [flask](http://flask.pocoo.org/) and some vanilla javascript.

    $ pip install -r requirements.txt
    $ python app.py
    # Go to http://localhost:5000 in your browser
