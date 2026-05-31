#!/usr/bin/env python3
"""阿里云 DDNS：同步 yoloworld.site 子域名 A 记录到当前公网 IP。"""

from __future__ import annotations

import json
import os
import sys

import requests
from aliyunsdkalidns.request.v20150109.AddDomainRecordRequest import (
    AddDomainRecordRequest,
)
from aliyunsdkalidns.request.v20150109.DescribeDomainRecordsRequest import (
    DescribeDomainRecordsRequest,
)
from aliyunsdkalidns.request.v20150109.UpdateDomainRecordRequest import (
    UpdateDomainRecordRequest,
)
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkcore.client import AcsClient

ACCESS_KEY_ID = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID", "")
ACCESS_KEY_SECRET = os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET", "")
DOMAIN_NAME = os.environ.get("DDNS_DOMAIN", "yoloworld.site")
SUB_DOMAINS = [
    s.strip()
    for s in os.environ.get("DDNS_SUBDOMAINS", "ani,config").split(",")
    if s.strip()
]
TTL = int(os.environ.get("DDNS_TTL", "600"))
REGION = os.environ.get("DDNS_REGION", "cn-hangzhou")


def get_public_ip() -> str | None:
    endpoints = [
        ("http://ifconfig.me/ip", lambda r: r.text.strip()),
        ("http://myip.ipip.net", lambda r: r.text.split("：")[-1].split()[0].strip()),
        ("http://api.ipify.org", lambda r: r.text.strip()),
        ("https://api.ipify.org?format=json", lambda r: r.json().get("ip")),
        ("https://ifconfig.me/all.json", lambda r: r.json().get("ip_addr")),
    ]
    for url, parser in endpoints:
        try:
            response = requests.get(
                url,
                timeout=8,
                proxies={"http": None, "https": None},
            )
            response.raise_for_status()
            ip = parser(response)
            if ip and "." in ip:
                return ip
        except Exception as exc:
            print(f"从 {url} 获取 IP 失败: {exc}")
    return None


def find_a_record(client: AcsClient, rr: str) -> dict | None:
    request = DescribeDomainRecordsRequest()
    request.set_DomainName(DOMAIN_NAME)
    request.set_RRKeyWord(rr)
    request.set_TypeKeyWord("A")
    response = json.loads(client.do_action_with_exception(request))
    records = response.get("DomainRecords", {}).get("Record", [])
    if isinstance(records, dict):
        records = [records]
    for record in records:
        if record.get("RR") == rr and record.get("Type") == "A":
            return record
    return None


def upsert_a_record(client: AcsClient, rr: str, current_ip: str) -> bool:
    record = find_a_record(client, rr)
    if record:
        record_id = record["RecordId"]
        old_ip = record.get("Value")
        if old_ip == current_ip:
            print(f"[{rr}.{DOMAIN_NAME}] IP 未变 ({current_ip})，跳过")
            return True
        print(f"[{rr}.{DOMAIN_NAME}] 更新: {old_ip} -> {current_ip}")
        request = UpdateDomainRecordRequest()
        request.set_RecordId(record_id)
        request.set_RR(rr)
        request.set_Type("A")
        request.set_Value(current_ip)
        request.set_TTL(TTL)
        client.do_action_with_exception(request)
        print(f"[{rr}.{DOMAIN_NAME}] 更新成功")
        return True

    print(f"[{rr}.{DOMAIN_NAME}] 记录不存在，正在创建...")
    request = AddDomainRecordRequest()
    request.set_DomainName(DOMAIN_NAME)
    request.set_RR(rr)
    request.set_Type("A")
    request.set_Value(current_ip)
    request.set_TTL(TTL)
    client.do_action_with_exception(request)
    print(f"[{rr}.{DOMAIN_NAME}] 创建成功")
    return True


def main() -> int:
    if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET:
        print("错误: 请设置 ALIBABA_CLOUD_ACCESS_KEY_ID / ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        return 1

    print(f"域名: {DOMAIN_NAME}")
    print(f"子域名: {', '.join(SUB_DOMAINS)}")
    override = os.environ.get("DDNS_PUBLIC_IP", "").strip()
    if override:
        ip = override
        print(f"使用 DDNS_PUBLIC_IP 固定公网 IP: {ip}")
    else:
        print("正在获取公网 IP...")
        ip = get_public_ip()
        if not ip:
            print("无法获取公网 IP")
            return 1
        print(f"当前公网 IP: {ip}")
        print("提示: 仅在路由器 WAN 下跑 DDNS；热点会写错 IP。可设 DDNS_PUBLIC_IP=家里公网 IP")

    client = AcsClient(ACCESS_KEY_ID, ACCESS_KEY_SECRET, REGION)
    ok = True
    try:
        for rr in SUB_DOMAINS:
            if not upsert_a_record(client, rr, ip):
                ok = False
    except (ClientException, ServerException) as exc:
        print(f"阿里云 API 失败: {exc}")
        return 1

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
