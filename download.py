#!/usr/bin/env python3

import json
import os
import re
import requests
import shutil
import subprocess
from urllib.parse import urlsplit

import fdroidserver.common
import fdroidserver.index

def main():
  with open("apks.json") as file:
    apks = json.load(file)
  with open("cache/versions.json") as file:
    versions = json.load(file)
  for apk in apks:
    ver = ""
    ignore = False
    if "version" in apk:
      verObj = apk["version"]
      if "json" in verObj:
        ver = get_version_json(verObj["url"], verObj["json"])
      elif "regex" in verObj:
        ver = get_version_regex(verObj["url"], verObj["regex"])
      elif "fdroid" in verObj:
        ver = get_version_fdroid(apk["baseUrl"].format(ver=""), verObj["fdroid"])
      if apk["name"] in versions and ver == versions[apk["name"]]:
        continue
      versions[apk["name"]] = ver
    print("Downloading " + apk["name"] + " " + ver)
    if "ignoreErrors" in apk:
      ignore = apk["ignoreErrors"]
    if "architectures" in apk:
      for arch in apk["architectures"]:
        download(apk["name"] + ".apk", apk["baseUrl"].format(arch=arch, ver=ver), ignore)
    else:
      download(apk["name"] + ".apk", apk["baseUrl"].format(ver=ver), ignore)
  with open('cache/versions.json', 'w') as file:
    json.dump(versions, file, ensure_ascii=False)

def download(name, download_url, ignore):
  if download_url.endswith(".apk"):
    if os.path.isfile("fdroid/repo/" + name):
      os.rename("fdroid/repo/" + name, "fdroid/repo/" + os.path.split(urlsplit(download_url).path)[-1])
    retcode = subprocess.call(["wget", "--progress=dot:mega", "-N", "-P", "fdroid/repo", download_url])
    os.rename("fdroid/repo/" + os.path.split(urlsplit(download_url).path)[-1], "fdroid/repo/" + name)
  else:
    retcode = subprocess.call(["wget", "--progress=dot:mega", "-nc", "--content-disposition", "-P", "fdroid/repo", download_url])
  if not ignore and retcode != 0:
    raise Exception("Failed downloading " + download_url)

def get_version_regex(url, query):
  request = requests.get(url)
  regex = re.search(query, request.text)
  return regex.group(1)

def get_version_json(url, query):
  request = requests.get(url)
  version = request.json()
  if not isinstance(query, list):
    return version[query]
  for query_part in query:
    version = version[query_part]
  return version

def get_version_fdroid(url, query):
  fdroidserver.common.config = {}
  fdroidserver.common.config['jarsigner'] = shutil.which('jarsigner')
  # TODO Add fingerprint, and use etag
  data, etag = fdroidserver.index.download_repo_index(url, None, False)
  for app in data['apps']:
    if app['packageName'] == query:
      for apk in data['packages'][app['packageName']]:
        # No idea why suggestedVersionCode is a string
        if apk['versionCode'] == int(app['suggestedVersionCode']):
          return apk['apkName']
      return data['packages'][app['packageName']][0]['apkName']

if __name__ == "__main__":
  main()
