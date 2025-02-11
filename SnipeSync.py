#!python3

#
# Copyright (c) Michael Kelly. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for details.
#

import json
import os
import string
import sys
import random
import time
from urllib.parse import quote
from pymosyle import MosyleAPI
import requests
from loguru import logger

config = {}
snipe_assets = {}
snipe_headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}


def get_or_create_snipe_user(first_name, last_name, username, email):
    # Lets look in Snipe
    logger.debug(f"Looking user email {email} to see if it already exists in Snipe")

    if "@" not in email:
        logger.error(f"Could not find user {email}, since it seems like this isn't an email address.")
        return 0

    response = requests.get(
        f"{config['snipe']['base_url']}/users?limit=1&offset=0&sort=created_at&order=desc&email={quote(email)}&deleted=false&all=false",
        headers=snipe_headers)

    if response.status_code != 200 and response.status_code != 404:
        # error
        logger.error(f"Received Snipe error when trying to find user {email}")
        logger.error(f"Search error returned {response.status_code}; {response.content}")
        raise Exception("Snipe did not return success on this search")

    if response.status_code != 404:
        response_json = json.loads(response.content)

    if response.status_code == 404 and len(response_json['rows']) == 0:
        if not config['snipe']['create_users']:
            logger.warning(f"Could not find user {email}, but creating users is disabled.")
            return 0

        logger.debug("User does not already exist, creating...")
        password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=25))
        data = {
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "password": password,
            "password_confirmation": password,
            "email": email,
            "activated": True
        }
        response = requests.post(f"{config['snipe']['base_url']}/users", headers=snipe_headers, data=json.dumps(data))

        if response.status_code == 200 or response.status_code == 201:
            response_json = json.loads(response.content)
            row = response_json['payload']
            if response_json['status'] == "error":
                logger.error(response_json['messages'])
                raise Exception("Snipe returned an error during the transaction.")
            logger.debug(f"Created new user {email} in Snipe, new ID is {row['id']}")
            return row['id']
        else:
            logger.error("Problem creating new Snipe user!")
            raise Exception("Problem creating new Snipe user!")
    else:
        row = response_json['rows'][0]
        logger.debug(f"Matched {email} to Snipe User ID {row['id']}")
        return row['id']


def get_or_create_snipe_model(model_name, model_number, category_id):
    # Check to see if the model name is already cached
    if model_name in snipe_assets.keys():
        return snipe_assets[model_name]

    # If not, lets look in Snipe
    logger.debug(f"Looking model name {model_name} to see if it already exists in Snipe")

    response = requests.get(
        f"{config['snipe']['base_url']}/models?limit=10&offset=0&search={quote(model_name)}&sort=created_at&order=asc",
        headers=snipe_headers)

    if response.status_code != 200 and response.status_code != 404:
        # error
        logger.error(f"Received Snipe error when trying to find model {model_name}")
        logger.error(f"Search error returned {response.status_code}; {response.content}")
        time.sleep(1)
        raise Exception("Snipe did not return success on this search")

    if response.status_code != 404:
        response_json = json.loads(response.content)

    if response.status_code == 404 or len(response_json['rows']) == 0:
        logger.debug("Model name does not already exist, creating...")
        data = {
            "name": model_name,
            "notes": model_number,
            "category_id": category_id,
            "manufacturer_id": config['snipe']['apple_manufacturer_id']
        }
        response = requests.post(f"{config['snipe']['base_url']}/models", headers=snipe_headers, data=json.dumps(data))

        if response.status_code == 200 or response.status_code == 201:
            response_json = json.loads(response.content)
            row = response_json['payload']
            if response_json['status'] == "error":
                logger.error(response_json['messages'])
                raise Exception("Snipe returned an error during the transaction.")
            snipe_assets[model_name] = row['id']
            logger.debug(f"Created model {model_name} in Snipe, new ID is {row['id']}")
            return row['id']
        else:
            logger.error("Problem creating new Snipe model!")
            raise Exception("Problem creating new Snipe model!")
    else:
        row = response_json['rows'][0]
        snipe_assets[model_name] = row['id']
        logger.debug(f"Matched {model_name} to Snipe Model ID {row['id']}")
        return row['id']


def get_snipe_asset(serial_number):
    # Lookup the snipe ID first just in case the asset already exists
    logger.debug(f"Looking serial number {serial_number} to see if it already exists in Snipe")

    response = requests.get(
        f"{config['snipe']['base_url']}/hardware/byserial/{quote(serial_number)}?deleted=false",
        headers=snipe_headers)

    if response.status_code != 200 and response.status_code != 404:
        # error
        logger.warning(f"Received Snipe error when trying to find asset {serial_number}")
        logger.warning(f"Search error returned {response.status_code}; {response.content}")
        return None

    if response.status_code != 404:
        response_json = json.loads(response.content)
        if 'status' in response_json.keys() and response_json['status'] == "error":
            return None

        if 'rows' in response_json.keys() and len(response_json['rows']) > 0:
            row = response_json['rows'][0]
            return row

    return None


def checkout_snipe_asset(asset_id, user_id):
    if user_id == 0:
        # This will be a checkin
        data = {
            "status_id": config['snipe']['default_status_id'],
            "note": "Automated checkin by Mosyle->Snipe sync"
        }
        logger.debug(f"Checking in asset id {asset_id}")
        response = requests.post(f"{config['snipe']['base_url']}/hardware/{asset_id}/checkin", headers=snipe_headers,
                                 data=json.dumps(data))

        if response.status_code == 200 or response.status_code == 201:
            response_json = json.loads(response.content)
            if response_json['status'] == "error":
                if response_json['messages'] == "That asset is already checked in.":
                    logger.debug("Asset is already checked in.")
                    return True

                logger.error(response_json['messages'])
                raise Exception("Snipe returned an error during the transaction.")
            return True
        else:
            logger.error("Problem checking in snipe asset!")
            raise Exception("Problem checking in snipe asset!")
    else:
        # This will be a checkout
        # Make sure it is checked in first
        checkout_snipe_asset(asset_id, 0)

        data = {
            "checkout_to_type": "user",
            "status_id": config['snipe']['default_status_id'],
            "assigned_user": user_id,
            "note": "Automated checkout by Mosyle->Snipe sync"
        }
        logger.debug(f"Checking out asset id {asset_id} to {user_id}")
        response = requests.post(f"{config['snipe']['base_url']}/hardware/{asset_id}/checkout", headers=snipe_headers,
                                 data=json.dumps(data))

        if response.status_code == 200 or response.status_code == 201:
            response_json = json.loads(response.content)
            if response_json['status'] == "error":
                logger.error(response_json['messages'])
                raise Exception("Snipe returned an error during the transaction.")
            return True
        else:
            logger.error("Problem checking in snipe asset!")
            raise Exception("Problem checking in snipe asset!")


def create_or_update_snipe_asset(serial_number, data):
    # Lookup the snipe ID first just in case the asset already exists
    row = get_snipe_asset(serial_number)

    if row is None:
        logger.debug("Asset does not already exist, creating...")
        response = requests.post(f"{config['snipe']['base_url']}/hardware", headers=snipe_headers, data=json.dumps(data))

        if response.status_code == 200 or response.status_code == 201:
            response_json = json.loads(response.content)
            row = response_json['payload']
            if response_json['status'] == "error":
                logger.error(response_json['messages'])
                raise Exception("Snipe returned an error during the transaction.")
            logger.info(f"Created new asset {data['asset_tag']} with serial {serial_number} and ID {row['id']}")
            return row
        else:
            logger.error("Problem creating new Snipe asset!")
            raise Exception("Problem creating new Snipe asset!")
    else:
        values_changed = False
        # Check these keys for changes only
        for key in ["asset_tag", "notes", "name"]:
            if key == "notes" and data[key] in row[key]:
                continue
            if row[key] != data[key]:
                values_changed = True

        if values_changed:
            logger.debug(f"Asset already exists in snipe as ID {row['id']}, proceeding with update")
            response = requests.patch(f"{config['snipe']['base_url']}/hardware/{row['id']}", headers=snipe_headers,
                                     data=json.dumps(data))

            if response.status_code == 200 or response.status_code == 201:
                response_json = json.loads(response.content)
                if response_json['status'] == "error":
                    logger.error(response_json['messages'])
                    raise Exception("Snipe returned an error during the transaction.")
                row = response_json['payload']
                logger.info(f"Updated asset {data['asset_tag']} with serial {serial_number} and ID {row['id']}")
                return row
            else:
                logger.error("Problem updating Snipe asset!")
                raise Exception("Problem updating Snipe asset!")
        else:
            logger.debug(f"Asset already exists in snipe as ID {row['id']}, no update required")
            return row


# Load configuration details from file
if not os.path.exists("config.json"):
    logger.error("Unable to find config.json!")
    sys.exit(1)
with open("config.json", "r") as config_file:
    config = json.loads(config_file.read())

# Set logging level
if 'log_level' in config.keys():
    logger.remove()
    logger.add(sys.stdout, level=config['log_level'])

# Setup the Mosyle connection
logger.info("Trying to setup Mosyle connection")
api = MosyleAPI(config['mosyle']['access_token'], config['mosyle']['email'], config['mosyle']['password'])
if not api.retrieve_jwt():
    logger.error("Unable to successfully obtain a JWT from Mosyle; Check credentials!")
    sys.exit(1)

# Setup the Snipe connection
# Just a blank search to verify the credentials are valid
logger.info("Trying to setup Snipe connection")
snipe_headers['Authorization'] = f"Bearer {config['snipe']['api_token']}"
response = requests.get(f"{config['snipe']['base_url']}/models?limit=1&offset=0&sort=created_at&order=asc",
                        headers=snipe_headers)
if response.status_code != 200:
    logger.error("Unable to successfully connect to the Snipe API!")
    logger.error(f"Received HTTP error {response.status_code}")
    sys.exit(1)


def process_ios():
    # Start retrieving iOS devices
    if config['snipe']['import_ios']:
        logger.info("Retrieving iOS devices from Mosyle")
        devices = api.get_devices("ios")

        # Preload the models into Snipe
        for device in devices:
            if 'device_model_name' not in device.keys():
                continue
            get_or_create_snipe_model(device['device_model_name'], device['device_model'], config['snipe']['ios_category_id'])

        # Actually import the iOS devices
        for device in devices:
            if 'device_model_name' not in device.keys():
                continue
            snipe_model_id = snipe_assets[device['device_model_name']]

            data = {
                "archived": False,
                "supplier_id": config['snipe']['apple_supplier_id'],
                "asset_tag": device['asset_tag'],
                "status_id": config['snipe']['default_status_id'],
                "model_id": snipe_model_id,
                "name": device['device_name'],
                "serial": device['serial_number'],
                "notes": device['open_direct_device_link']
            }

            try:
                snipe_device_details = create_or_update_snipe_asset(device['serial_number'], data)
                time.sleep(config['snipe']['rate_limit'])

                if config['snipe']['checkout_devices']:
                    if 'useremail' not in device.keys() or device['useremail'].strip() == "":
                        # Device is not checked out
                        # Make sure it is checked in in Snipe
                        checkout_snipe_asset(snipe_device_details['id'], 0)
                    else:
                        # Get the snipe ID to checkout to
                        name_parts = device['username'].split(" ")
                        if len(name_parts) == 2:
                            first_name = name_parts[0]
                            last_name = name_parts[1]
                        elif len(name_parts) == 3:
                            first_name = name_parts[0]
                            last_name = name_parts[2]
                        else:
                            first_name = name_parts[0]
                            last_name = name_parts[len(name_parts) - 1]
                        snipe_user_id = get_or_create_snipe_user(first_name, last_name, device['useremail'],
                                                                 device['useremail'])

                        if snipe_user_id == 0:
                            checkout_snipe_asset(snipe_device_details['id'], 0)
                        else:
                            # Make sure it isn't already checked out to them
                            snipe_device = get_snipe_asset(device['serial_number'])
                            if snipe_device['assigned_to'] is None or snipe_device['assigned_to']['id'] != snipe_user_id:
                                logger.info(f"Checking {device['serial_number']} out to {device['useremail']}.")
                                checkout_snipe_asset(snipe_device_details['id'], snipe_user_id)
                            else:
                                logger.info("Device is already correctly checked out.")
            except Exception as e:
                logger.error(f"Exception raised while processing device {device['serial_number']}")
                logger.error("Will be skipped!")
                logger.debug(e)


def process_macos():
    # Start retrieving macOS devices
    if config['snipe']['import_macos']:
        logger.info("Retrieving macOS devices from Mosyle")
        devices = api.get_devices("mac")

        # Preload the models into Snipe
        for device in devices:
            if 'device_model_name' not in device.keys():
                continue
            get_or_create_snipe_model(device['device_model_name'], device['device_model'], config['snipe']['macos_category_id'])

        # Actually import the macOS devices
        for device in devices:
            if 'device_model_name' not in device.keys():
                continue
            snipe_model_id = snipe_assets[device['device_model_name']]

            data = {
                "archived": False,
                "supplier_id": config['snipe']['apple_supplier_id'],
                "asset_tag": device['asset_tag'],
                "status_id": config['snipe']['default_status_id'],
                "model_id": snipe_model_id,
                "name": device['device_name'],
                "serial": device['serial_number'],
                "notes": device['open_direct_device_link']
            }

            try:
                snipe_device_details = create_or_update_snipe_asset(device['serial_number'], data)
                time.sleep(config['snipe']['rate_limit'])

                if config['snipe']['checkout_devices']:
                    if 'useremail' not in device.keys() or device['useremail'].strip() == "":
                        # Device is not checked out
                        # Make sure it is checked in in Snipe
                        checkout_snipe_asset(snipe_device_details['id'], 0)
                    else:
                        # Get the snipe ID to checkout to
                        name_parts = device['username'].split(" ")
                        if len(name_parts) == 2:
                            first_name = name_parts[0]
                            last_name = name_parts[1]
                        elif len(name_parts) == 3:
                            first_name = name_parts[0]
                            last_name = name_parts[2]
                        else:
                            first_name = name_parts[0]
                            last_name = name_parts[len(name_parts) - 1]
                        snipe_user_id = get_or_create_snipe_user(first_name, last_name, device['useremail'],
                                                                 device['useremail'])

                        if snipe_user_id == 0:
                            checkout_snipe_asset(snipe_device_details['id'], 0)
                        else:
                            # Make sure it isn't already checked out to them
                            snipe_device = get_snipe_asset(device['serial_number'])
                            if snipe_device['assigned_to'] is None or snipe_device['assigned_to']['id'] != snipe_user_id:
                                logger.info(f"Checking {device['serial_number']} out to {device['useremail']}.")
                                checkout_snipe_asset(snipe_device_details['id'], snipe_user_id)
                            else:
                                logger.info("Device is already correctly checked out.")
            except Exception as e:
                logger.error(f"Exception raised while processing device {device['serial_number']}")
                logger.error("Will be skipped!")
                logger.debug(e)


def process_tvos():
    # Start retrieving tvOS devices
    if config['snipe']['import_tvos']:
        logger.info("Retrieving tvOS devices from Mosyle")
        devices = api.get_devices("tvos")

        # Preload the models into Snipe
        for device in devices:
            if 'device_model_name' not in device.keys():
                continue
            get_or_create_snipe_model(device['device_model_name'], device['device_model'], config['snipe']['tvos_category_id'])

        # Actually import the tvOS devices
        for device in devices:
            if 'device_model_name' not in device.keys():
                continue
            snipe_model_id = snipe_assets[device['device_model_name']]

            data = {
                "archived": False,
                "supplier_id": config['snipe']['apple_supplier_id'],
                "asset_tag": device['asset_tag'],
                "status_id": config['snipe']['default_status_id'],
                "model_id": snipe_model_id,
                "name": device['device_name'],
                "serial": device['serial_number'],
                "notes": device['open_direct_device_link']
            }

            try:
                snipe_device_details = create_or_update_snipe_asset(device['serial_number'], data)
                time.sleep(config['snipe']['rate_limit'])
            except Exception as e:
                logger.error(f"Exception raised while processing device {device['serial_number']}")
                logger.error("Will be skipped!")
                logger.debug(e)


process_ios()
process_macos()
process_tvos()
