#!/usr/bin/env python3
import requests
import json
from requests.auth import HTTPBasicAuth
import os

# import sqlite3
import csv
from datetime import datetime


headers = {"x-api-key": os.environ["JUMPCLOUD_API_KEY"], "content": "application/json"}


# creates new jumpcloud command
def create_command() -> str:
    url = "https://console.jumpcloud.com/api/commands"
    payload = {
        "command": "#!/bin/bash\nls /Applications",
        "commandType": "mac",
        "LaunchType": "manual",
        "name": "pull mac software",
        "sudo": True,
        # if you use 'root' you will get a 400 error.
        "user": "000000000000000000000000",
    }

    response = requests.request("POST", url, json=payload, headers=headers)
    commandID = json.loads(response.text)["_id"]
    return commandID


# binds the specified device group to the command
def bind_group(commandID: str, deviceGroupId: str):
    url = f"https://console.jumpcloud.com/api/v2/commands/{commandID}/associations"
    payload = {"id": deviceGroupId, "op": "add", "type": "system_group"}
    requests.request("POST", url, json=payload, headers=headers)


# runs command on binded devices and stores output into variable 'results'
def grab_current_software(commandID: str) -> dict:
    """run_url = "https://console.jumpcloud.com/api/runCommand"
    payload = {"_id": commandID}
    requests.request("POST", run_url, headers=headers, json=payload)"""

    get_url = f"https://console.jumpcloud.com/api/commands/{commandID}/results"
    query = {"limit": 100}
    results = json.loads(
        requests.request("GET", get_url, headers=headers, params=query).text
    )
    apps = {}
    system_url = "https://console.jumpcloud.com/api/systems/{id}"
    # grabs the applications and system_id from the results, and creates a dictionary with apps mapping to the system_id
    for item in results:
        pulled_apps = item["response"]["data"]["output"]
        system_id = item["system"]
        # grabbing device serial for auditing purposes
        system_url = f"https://console.jumpcloud.com/api/systems/{system_id}"
        queryString = {"fields": "serialNumber"}
        content = json.loads(
            requests.request(
                "GET", system_url, headers=headers, params=queryString
            ).text
        )
        serialNum = content["serialNumber"]
        apps[serialNum] = pulled_apps.split()

    return apps


# TODO (arek): add date to file report
def write_report(app_dict: dict):
    serials = app_dict.keys()
    with open("software_audit.csv", "w", newline="") as csv_file:
        reporter = csv.writer(csv_file)
        for item in serials:
            reporter.writerows(item[app_dict[item]])


# commandID = create_command()
# bind_group(commandID, "673cf3945525ed00011bf3ac")
write_report(grab_current_software("67606e79e8105bcf99bfde8b"))


"""def pull_device_list():
    url = f"https://a.simplemdm.com/api/v1/devices?limit=100"
    action = "w"
    # writing device names and ids:
    while True:
        device_content = requests.get(url, auth=HTTPBasicAuth(user_name, ""))
        device_content = json.loads(device_content.text)
        with open("lists/device_ids.txt", action) as open_file:
            for item in device_content["data"]:
                # filtering out old devices that haven't checked in for 3+ months
                date_string = item["attributes"]["last_seen_at"]
                device_date = datetime.fromisoformat(date_string)
                todays_date = datetime.today()
                if device_date.year < todays_date.year and device_date.month < 11:
                    continue
                elif todays_date.month - device_date.month >= 2:
                    continue
                else:
                    # if not older than 3 months, add to file
                    device_name = item["attributes"]["name"]
                    device_name = device_name.replace(" ", "_")
                    device_id = item["id"]
                    open_file.write(f"{device_name} {device_id}\n")
        # updating url if there are more devices
        if device_content["has_more"] == True:
            last_id = device_content["data"][-1]["id"]
            url = f"https://a.simplemdm.com/api/v1/devices?limit=100&starting_after={last_id}"
            action = "a"
        else:
            break


# creating DB
def create_db():
    con = sqlite3.connect("software.db")
    cur = con.cursor()

    # creating table if not created yet
    result = cur.execute("SELECT name FROM sqlite_master WHERE name='inventory'")
    if result.fetchone() == None:
        cur.execute("CREATE TABLE inventory(device_name, device_id, app_name, date)")
    con.close()


# adding data to db
def add_data(data):
    con = sqlite3.connect("software.db")
    cur = con.cursor()
    cur.executemany("INSERT INTO inventory VALUES(?, ?, ?, ?)", data)
    con.commit()
    con.close()


# API call to grab applications from DEVICE_ID
def grab_apps():
    app_data = []
    # iterating over each device id to put apps into DB
    with open("lists/device_ids.txt", "r") as open_file:
        ids = open_file.readlines()

        for line in ids:
            # creating the device name, some names have underscores so we have to reformat to prevent issues
            line = line.split()
            DEVICE_ID = line[-1]
            device_name = line[0]
            url = f"https://a.simplemdm.com/api/v1/devices/{DEVICE_ID}/installed_apps?limit=100"

            while True:
                # coverting from json to dictionary
                content = requests.get(url, auth=HTTPBasicAuth(user_name, ""))
                content = json.loads(content.text)

                # filtering out data that I want

                for item in content["data"]:
                    app_name = item["attributes"]["name"]
                    # creating a list with default mac apps
                    with open("lists/approved_software.txt", "r") as open_file:
                        approved_items = [
                            item.strip() for item in open_file.readlines()
                        ]
                    # checking if current app_name is in approved list
                    if app_name in approved_items:
                        continue
                    else:
                        item_date = item["attributes"]["last_seen_at"].replace(
                            ".000Z", ""
                        )
                        date = datetime.strptime(item_date, f"%Y-%m-%dT%H:%M:%S")
                        new_date = datetime.strftime(date, f"%Y-%m-%d")

                        app_data.append((device_name, DEVICE_ID, app_name, new_date))

                if content["has_more"] == True:
                    last_id = content["data"][-1]["id"]
                    url = f"https://a.simplemdm.com/api/v1/devices/{DEVICE_ID}/installed_apps?limit=100&starting_after={last_id}"
                elif content["has_more"] == False:
                    break
    return app_data"""


# bind_group("674e01abe71c335713d0eabe", "673cf3945525ed00011bf3ac")
# pull_device_list()
# create_db()
# add_data(grab_apps())
