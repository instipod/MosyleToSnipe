# MosyleToSnipe
A simple Python script to sync device data from Mosyle Manager to the Snipe-IT inventory management system.
It is intended to run on a schedule (e.g. nightly).

## Getting started
Clone the repo

`git clone https://github.com/instipod/MosyleToSnipe.git`

Grab a copy of the pymosyle class and put it in the same folder (to be made a module soon)

`wget https://raw.githubusercontent.com/instipod/pymosyle/refs/heads/main/pymosyle.py`

Copy the config.json.example to config.json and supply information about your Mosyle and Snipe accounts.
This tool will sync data to Snipe quite fast, if you run your own Snipe server, increase the default API rate limit by adding the following to your .env file:

`API_THROTTLE_PER_MINUTE=1000`

If you use Snipe cloud and cannot adjust this setting, increase snipe rate_limit in the config.json file.  This will make your syncs slower, but you won't hit rate limits.

Run the script

`python3 SnipeSync.py`