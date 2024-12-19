#!/usr/bin/env python3
import requests
from json import loads
from os import environ
from subprocess import run, PIPE
import sqlite3
from datetime import date

# Globals:
headers = {"x-api-key": environ["JUMPCLOUD_API_KEY"], "content": "application/json"}
bad_apps = []


def create_command() -> str:
    url = "https://console.jumpcloud.com/api/commands"
    payload = {
        "command": "#!/bin/bash\nls /Applications",
        "commandType": "mac",
        "LaunchType": "manual",
        "name": "Pull Software - Macs",
        "sudo": True,
        # if you use 'root' you will get a 400 error.
        "user": "000000000000000000000000",
    }

    response = requests.request("POST", url, json=payload, headers=headers)
    commandID = loads(response.text)["_id"]
    return commandID


def bind_group(commandID: str, deviceGroupId: str):
    url = f"https://console.jumpcloud.com/api/v2/commands/{commandID}/associations"
    payload = {"id": deviceGroupId, "op": "add", "type": "system_group"}
    requests.request("POST", url, json=payload, headers=headers)


def run_command(commandID: str) -> int:
    run_url = "https://console.jumpcloud.com/api/runCommand"
    payload = {"_id": commandID}
    return requests.request("POST", run_url, headers=headers, json=payload).status_code


# grabs results from command stores output into variable 'results'
def grab_command_results(commandID: str) -> dict:
    results_url = f"https://console.jumpcloud.com/api/commands/{commandID}/results"
    resultsQuery = {"limit": 100, "skip": 100}
    # TODO (arek): need to make a way to retrieve records after the initial 100
    results = loads(
        requests.request("GET", results_url, headers=headers, params=resultsQuery).text
    )
    return results


def collect_report_data(results: dict) -> list:
    # formats approved apps for comparison
    report_data = []
    with open("approved_software.txt", "r") as openfile:
        approved_apps = openfile.readlines()
        for item in approved_apps:
            approved_apps[approved_apps.index(item)] = item.rstrip("\n")

        # compares the found applications to the approved list, and stores the unapproved ones in 'bad_apps'

        # uncompliant_devices = []
        for item in results:
            system_id = item["system"]
            pulled_apps = item["response"]["data"]["output"].split("\n")

            # uses system_id to grab device serial
            system_url = f"https://console.jumpcloud.com/api/systems/{system_id}"
            queryString = {"fields": "serialNumber"}
            content = loads(
                requests.request(
                    "GET", system_url, headers=headers, params=queryString
                ).text
            )
            serialNum = content["serialNumber"]
            for item in pulled_apps:
                if item not in approved_apps and item not in bad_apps:
                    bad_apps.append(item)
                    report_data.append((system_id, serialNum, item))

                    """if system_id not in uncompliant_devices:
                        uncompliant_devices.append(system_id)"""
            # report_data.append((system_id, serialNum, device_apps))

    return report_data
    # apps[serialNum] = pulled_apps.split()


def create_database():
    # creating databaseß
    con = sqlite3.connect("software.db")
    cur = con.cursor()

    # checking if table is created yet
    result = cur.execute("SELECT name FROM sqlite_master WHERE name='inventory'")
    if result.fetchone() == None:
        cur.execute("CREATE TABLE inventory(system_id, serial, apps)")
    con.close()


def create_report(results: list):
    con = sqlite3.connect("software.db")
    cur = con.cursor()
    cur.executemany("INSERT INTO inventory VALUES(?, ?, ?)", results)
    con.commit()
    con.close()
    with open(f"{date.today()}_software_report.csv", "w") as softwarereport:
        report = run(
            [
                "sqlite3",
                "software.db",
                "-csv",
                "-header",
                "select * from inventory;",
            ],
            text=True,
            stdout=PIPE,
        )
        softwarereport.write(report.stdout)


# commandID = create_command()
# bind_group(commandID, "673cf3945525ed00011bf3ac")
create_database()
create_report(collect_report_data(grab_command_results("67606e79e8105bcf99bfde8b")))
