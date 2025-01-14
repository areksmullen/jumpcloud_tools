#!/usr/bin/env python3
# Objective: Audits company MacOS software and Creates report in S3
# Arek Smullen (arek.smullen@sheerid.com)
# SheerID 2025

from requests import request
from json import loads
from os import environ
from subprocess import run, PIPE
import sqlite3
from datetime import date
from boto3 import client

# TODO (arek): add exception handling
# Globals:
bad_apps = []
resultIds = []
region = "us-east-1"
environ["AWS_DEFAULT_REGION"] = region
# TODO (arek): replace with correct bucket in prod aws
bucket = "arekgcpscoutsuite"
app_file = "approved_software.txt"
reportFile = f"{date.today()}_software_report.csv"
# This will need to be periodically updated as we scale up.
macDevices = 200


def get_secret():
    secret_name = "jc-api-key"
    region_name = "us-east-1"
    # Create a Secrets Manager client
    secrets_manager = client(service_name="secretsmanager", region_name=region_name)
    get_secret_value_response = secrets_manager.get_secret_value(SecretId=secret_name)
    secret = loads(get_secret_value_response["SecretString"])
    return secret["Jumpcloud-API-key"]


def grab_approved_list():
    s3 = client("s3")
    bucket = "arekgcpscoutsuite"
    s3.download_file(Filename=app_file, Bucket=bucket, Key=app_file)


# grabs results from command stores output into variable 'results'
def grab_command_results(commandID: str) -> dict:
    results_url = f"https://console.jumpcloud.com/api/commands/{commandID}/results"
    resultsQuery = {
        "limit": 100,
    }
    results = loads(
        request("GET", results_url, headers=headers, params=resultsQuery).text
    )
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


# grabs result ids from results and puts them in the 'resultIds' list
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
    s3 = client("s3")
    s3.upload_file(Filename=reportFile, Bucket=bucket, Key=reportFile)


def clear_command_results(result_ids: list):
    for result in result_ids:
        url = f"https://console.jumpcloud.com/api/commandresults/{result}"
        request("DELETE", url, headers=headers).raise_for_status


cmdId = "67606e79e8105bcf99bfde8b"
headers = {"x-api-key": get_secret(), "content": "application/json"}
grab_approved_list()
create_database()
create_report(collect_report_data(hijack_resultsids(grab_command_results({cmdId}))))
clear_command_results(resultIds)
