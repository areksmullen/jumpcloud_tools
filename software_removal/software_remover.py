#!/usr/bin/env python3
# Objective: Deletes unapproved applications from company devices
# Arek Smullen (arek.smullen@sheerid.com)
# SheerID 2025

from os import environ
import requests
from datetime import datetime
from csv import reader
from boto3 import client
import re


# Globals
bucket = "sheerid-logarchive-use1"
region = "us-east-1"
environ["AWS_DEFAULT_REGION"] = region

system_ids = []


# grabs latest file from S3
def grab_file():
    prefix = "it/software-inventory/"
    s3 = client("s3")
    # List all objects in the bucket with the specified prefix
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    if "Contents" not in response:
        print(f"No files found in bucket {bucket} with prefix {prefix}")
        return None

    latest_file = None
    latest_date = None

    # Define a regex pattern to extract date from the file name
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2})_software_report\.csv")

    for obj in response["Contents"]:
        file_name = obj["Key"]

        # Search for files matching the pattern
        match = pattern.search(file_name)
        if match:
            file_date = match.group(1)

            # Convert date string to a datetime object for comparison
            file_date_dt = datetime.strptime(file_date, "%Y-%m-%d")

            # Compare dates to find the most recent one
            if latest_date is None or file_date_dt > latest_date:
                latest_date = file_date_dt
                latest_file = file_name

    if not latest_file:
        print("No matching report files found.")
        return None

    s3.download_file(Bucket=bucket, Key=latest_file, Filename="./apps.csv")


app_list = []


def grab_apps_and_systems(file, list1, list2):
    with open("apps.csv", "r") as app_file:
        contents = reader(app_file)
        app_list = list1
        system_ids = list2
        for line in contents:
            app = line[2]
            system = line[0]
            if line[0] == "system_id":
                continue
            else:
                app_list.append(f'"{app}"')
                system_ids.append(system)
    app_list = set(app_list)
    system_ids = set(system_ids)


def create_jc_command(apps):
    apps = " ".join(apps)
    url = "https://console.jumpcloud.com/api/commands"
    headers = {
        "x-api-key": environ["JUMPCLOUD_API_KEY"],
        "content": "application/json",
    }
    cmd_string_one = f"""
    #!/bin/bash
    declare -a app_list
    app_list=({apps})"""

    cmd_string_two = """
    for app in ${app_list[@]}:
    do
        if [ -e /Applications/$app ]; then
          chmod 000 /Applications/$app
        else
          continue
        fi
    done
    """
    cmd_string = cmd_string_one + cmd_string_two
    payload = {
        "command": cmd_string,
        "commandType": "mac",
        "name": "test delete apps",
        "sudo": True,
        "user": "000000000000000000000000",
    }
    requests.request("POST", url=url, json=payload, headers=headers).status_code


# TODO(arek): create function that binds devices from
# system_ids to the newly created_command. (should grab the id for the command)


reportFile = "apps.csv"
# grab_apps_and_systems(reportFile, app_list, system_ids)
# create_jc_command(app_list)
