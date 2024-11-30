# -*- coding: utf-8 -*-
import asyncio
import os
import re
from enum import Enum
import re
import requests
from enum import Enum
from datetime import datetime, timezone

import botpy
from botpy import logging
from botpy.ext.command_util import Commands

from botpy.ext.cog_yaml import read
from botpy.message import GroupMessage, Message

# Notion API设置
# 从config.yaml读取变量
test_config = read(os.path.join(os.path.dirname(__file__), "config.yaml"))
NOTION_TOKEN = test_config["NOTION_TOKEN"]
MEMBER_DATABASE_ID = test_config["MEMBER_DATABASE_ID"]
LOG_DATABASE_ID = test_config["LOG_DATABASE_ID"]
PROGRESS_DATABASE_ID = test_config["PROGRESS_DATABASE_ID"]
# member_openid = '8E2E8922A7072119506D8361B78181E3'
member_data = []

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

proxies = {"http": None, "https": None}

test_config = read(os.path.join(os.path.dirname(__file__), "config.yaml"))

_log = logging.get_logger()


class CommandType(Enum):
    LOG = "/log"
    PROGRESS = "/进度"
    INIT = "/init"


def match_command(input_str):
    # 构造一个正则表达式模式，用于匹配命令
    pattern = "|".join([re.escape(command.value) for command in CommandType])

    # 使用re.search来查找匹配的命令
    match = re.search(pattern, input_str)

    if match:
        # 如果找到匹配，返回命令和剩余的字符串
        matched_command = match.group(0)
        for command in CommandType:
            if command.value == matched_command:
                remaining_str = input_str[match.end():].strip()  # 剩余的字符串
                return {matched_command: remaining_str}
    return None

def extract_numbers(input_string):
    # 使用正则表达式提取所有数字字符
    return ''.join(re.findall(r'\d', input_string))


def update_page(page_id: str, data: dict):
    url = f"https://api.notion.com/v1/pages/{page_id}"

    payload = {"parent": {"database_id": MEMBER_DATABASE_ID}, "properties": data}

    res = requests.patch(url, json=payload, headers=headers, proxies=proxies)
    return res

def init_qq_id_pair(qq_number, member_openid):
    entry = get_entry_by_qq(qq_number)
    data = {
        "member_openid": {'type': 'rich_text',
                          'rich_text': [{'type': 'text', 'text': {'content': member_openid}}]},
    }
    update_page(entry["id"], data)

# 创建Notion页面的函数
def create_log(data: dict):
    create_url = "https://api.notion.com/v1/pages"

    payload = {"parent": {"database_id": LOG_DATABASE_ID}, "properties": data}

    res = requests.post(create_url, headers=headers, json=payload, proxies=proxies)
    print("Status Code:", res.status_code)
    print("Response:", res.json())  # 打印返回结果
    return res

def create_progress(data: dict):
    create_url = "https://api.notion.com/v1/pages"

    payload = {"parent": {"database_id": PROGRESS_DATABASE_ID}, "properties": data}

    res = requests.post(create_url, headers=headers, json=payload, proxies=proxies)
    print("Status Code:", res.status_code)
    print("Response:", res.json())  # 打印返回结果
    return res


# 处理命令并根据命令进行相关操作
def process_command(message):
    notion_userid: str
    group_name: str
    result = match_command(message.content)

    if result:
        command = list(result.keys())[0]  # 获取匹配到的命令
        remaining_str = result[command]  # 获取剩余的字符串

        if command == CommandType.INIT.value:
            qq_number = extract_numbers(remaining_str)
            init_qq_id_pair(qq_number, message.author.member_openid)
            print(f"Init command: {remaining_str}")
        else:
            user_info = get_entry_by_member_openid(message.author.member_openid)
            notion_userid = user_info['created_by']['id']
            group_name = user_info['properties']['组别']['select']['name']

        if command == CommandType.LOG.value:
            # 如果命令是/log，创建Notion页面
            print(f"Creating Notion page with log content: {remaining_str}")
            create_notion_log(remaining_str, notion_userid, group_name)
        elif command == CommandType.PROGRESS.value:
            print(f"Creating Notion page with Progress content: {remaining_str}")
            create_notion_progress(remaining_str, notion_userid, group_name)
        else:
            print(f"其他命令: {command}，内容: {remaining_str}")
    else:
        print("没有匹配到任何命令")


# 创建一个Notion页面，将日志内容作为属性
def create_notion_log(log_content: str, user_id=None, group_name=None):


    # 创建Notion页面的数据
    data = {
        "日志内容": {"title": [{"text": {"content": log_content}}]},
        'Status': {'type': 'status', 'status': {'name': '已记录'}},
        "关联人员": {'type': 'people', "people": [{"id": user_id}]},
        "关联组": {'type': 'multi_select', 'multi_select': [{'name': group_name}]},
    }

    # 调用create_page函数将数据发送到Notion
    create_log(data)

def create_notion_progress(progress_content: str, user_id=None, group_name=None):


    # 创建Notion页面的数据
    data = {
        "进度内容": {"title": [{"text": {"content": progress_content}}]},
        "关联人员": {'type': 'people', "people": [{"id": user_id}]},
        "关联组": {'type': 'multi_select', 'multi_select': [{'name': group_name}]},
    }

    # 调用create_page函数将数据发送到Notion
    create_progress(data)


def get_qq_by_member_openid(member_openid):
    # 遍历所有记录
    for entry in member_data:
        if entry['properties']['member_openid']['rich_text'][0]['text']['content'] == member_openid:
            return entry['properties']['qq号']['number']  # 返回找到的整条记录
    return None  # 如果没有找到对应的QQ号

def get_entry_by_member_openid(member_openid):
    # 遍历所有记录
    for entry in member_data:
        try:
            # 检查成员的 rich_text 是否存在且不为空
            if entry['properties']['member_openid']['rich_text'] and \
                    entry['properties']['member_openid']['rich_text'][0]['text']['content'] == member_openid:
                return entry
        except (KeyError, IndexError, TypeError) as e:
            # 捕获可能的键错误或索引错误，跳过这个条目
            print(f"Skipping entry due to error: {e}")
            continue
    return None # 如果没有找到对应的QQ号

def get_entry_by_qq(qq_number):
    # 遍历所有记录
    for entry in member_data:
        if entry['properties']['qq号']['rich_text'][0]['text']['content'] == qq_number:
            return entry  # 返回找到的整条记录
    return None  # 如果没有找到对应的QQ号

def get_user_and_group_by_qq(qq_number):
    # 遍历所有记录
    for entry in member_data:
        if entry['properties']['qq号']['rich_text'][0]['text']['content'] == qq_number:
            user_id = entry['properties']['回复者']['created_by']['id']
            group_name = entry['properties']['组别']['select']['name']
            return user_id, group_name
    return None, None

def get_pages(num_pages=None):
    """
    If num_pages is None, get all pages, otherwise just the defined number.
    """
    url = f"https://api.notion.com/v1/databases/{MEMBER_DATABASE_ID}/query"

    get_all = num_pages is None
    page_size = 100 if get_all else num_pages

    payload = {"page_size": page_size}
    response = requests.post(url, json=payload, headers=headers, proxies=proxies)

    data = response.json()

    # Comment this out to dump all data to a file
    # import json
    # with open('db.json', 'w', encoding='utf8') as f:
    #    json.dump(data, f, ensure_ascii=False, indent=4)

    results = data["results"]
    while data["has_more"] and get_all:
        payload = {"page_size": page_size, "start_cursor": data["next_cursor"]}
        url = f"https://api.notion.com/v1/databases/{MEMBER_DATABASE_ID}/query"
        response = requests.post(url, json=payload, headers=headers, proxies=proxies)
        data = response.json()
        results.extend(data["results"])

    return results


class MyClient(botpy.Client):
    async def on_ready(self):
        _log.info(f"robot 「{self.robot.name}」 on_ready!")



    async def on_group_at_message_create(self, message: GroupMessage):
        # _log.info(member_openid == message.author.member_openid)
        messageResult = await message._api.post_group_message(
            group_openid=message.group_openid,
              msg_type=0,
              msg_id=message.id,
              content=f"收到了消息：{message.content}")
        process_command(message)
        _log.info(messageResult)

    # async def on_group_at_message(self, message: GroupMessage):
    #     # 处理命令
    #     # process_command(message.content)
    #     messageResult = await message._api.post_group_message(
    #         group_openid=message.group_openid,
    #           msg_type=0,
    #           msg_id=message.id,
    #           content=f"收到了消息：{message.content}")
    #     _log.info(messageResult)


if __name__ == "__main__":
    # 通过预设置的类型，设置需要监听的事件通道
    # intents = botpy.Intents.none()
    # intents.public_messages=True

    member_data = get_pages()
    # 通过kwargs，设置需要监听的事件通道
    intents = botpy.Intents(public_messages=True)
    client = MyClient(intents=intents)
    client.run(appid=test_config["appid"], secret=test_config["secret"])