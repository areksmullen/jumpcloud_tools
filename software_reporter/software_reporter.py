#!/usr/bin/env python3
# Objective: Audits company MacOS software and Creates report in S3
# Arek Smullen (arek.smullen@sheerid.com)
# SheerID 2025

# this file has been modified to run locally 

from requests import request, exceptions
from json import loads
from os import environ
from subprocess import run, PIPE
import sqlite3
from datetime import date
from boto3 import client, Session

# Globals:
session = Session(profile_name="testing")
bad_apps = []
resultIds = []
region = "us-east-1"
environ["AWS_DEFAULT_REGION"] = region
bucket = "arekgcpscoutsuite"
app_file = "approved_software.txt"
reportFile = f"{date.today()}_software_report.csv"
# This will need to be periodically updated as we scale up.
macDevices = 200

def get_secret():
    # make sure this secret is named this in
    secret_name = "jc-api-key"
    region_name = "us-east-1"
    # Create a Secrets Manager client
    secrets_manager = session.client(service_name="secretsmanager", region_name=region_name)
    get_secret_value_response = secrets_manager.get_secret_value(SecretId=secret_name)
    secret = loads(get_secret_value_response["SecretString"])
    return secret["Jumpcloud-API-key"]


def grab_approved_list():
    s3 = session.client("s3")
    #bucket = "com-sheerid-it-statedb/software-inventory"
    s3.download_file(Filename=app_file, Bucket=bucket, Key=app_file)


def grab_command_results(commandID: str) -> dict:
    results_url = f"https://console.jumpcloud.com/api/commands/{commandID}/results"
    resultsQuery = {
        "limit": 100,
    }
    try:
        response = request("GET", results_url, headers=headers, params=resultsQuery)
        response.raise_for_status()
        results = loads(response.text)
    
    except exceptions.RequestException as e:
        print(f"Error retrieving command results: {e}")
    
    else:
        # "custom" pagination since JC doesn't have a good one.
        if len(results) < macDevices:
            resultsQuery = {
                "limit": 100,
                "skip": 100,
            }
            results_two = loads(
                request("GET", results_url, headers=headers, params=resultsQuery).text
            )
            results = results + results_two

    return results


def hijack_resultsids(results: dict) -> dict:
    for item in results:
        resultIds.append(item["response"]["id"])
    
    return results


def collect_report_data(results: dict) -> list:
    # formats approved apps for comparison
    report_data = []
    with open("approved_software.txt", "r") as openfile:
        approved_apps = openfile.readlines()
        for item in approved_apps:
            approved_apps[approved_apps.index(item)] = item.rstrip("\n")

        # compares the found applications to the approved list, and stores the unapproved ones in 'bad_apps'
        for item in results:
            system_id = item["system"]
            pulled_apps = item["response"]["data"]["output"].split("\n")

            # uses system_id to grab device serial
            system_url = f"https://console.jumpcloud.com/api/systems/{system_id}"
            queryString = {"fields": "serialNumber"}
            content = loads(
                request("GET", system_url, headers=headers, params=queryString).text
            )
            serialNum = content["serialNumber"]
            for item in pulled_apps:
                if item not in approved_apps and item not in bad_apps:
                    bad_apps.append(item)
                    report_data.append((system_id, serialNum, item))
    return report_data


def create_database():
    # creating database
    con = sqlite3.connect("software.db")
    cur = con.cursor()

    # checking if table is created yet
    result = cur.execute("SELECT name FROM sqlite_master WHERE name='inventory'")
    if result.fetchone() == None:
        cur.execute("CREATE TABLE inventory(system_id, serial, apps)")
    else:
        cur.execute("DROP TABLE inventory")
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
    s3 = session.client("s3")
    s3.upload_file(Filename=reportFile, Bucket=bucket, Key=reportFile)


def clear_command_results(result_ids: list):
    for result in result_ids:
        url = f"https://console.jumpcloud.com/api/commandresults/{result}"
        request("DELETE", url, headers=headers).raise_for_status


cmdId = "67c88ba02002cbf8c749184f"

headers = {"x-api-key": get_secret(), "content": "application/json"}
grab_approved_list()
create_database()
try:
    create_report(collect_report_data(hijack_resultsids(grab_command_results(cmdId))))
except Exception as err:
    print(f"Error: ${err}")
else:
    clear_command_results(resultIds)