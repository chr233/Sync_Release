'''
# @Author       : Chr_
# @Date         : 2022-04-25 12:46:01
# @LastEditors  : Chr_
# @LastEditTime : 2022-04-25 22:59:39
# @Description  : 检查GitHub与Gitee发行版, 下载缺失的发行版
'''

import asyncio
import pydantic
from asyncio import Semaphore
from aiohttp import ClientSession, FormData
from os import path, makedirs, listdir, rmdir, getenv
from base64 import b64encode
from typing import List
from models.gitee import Gitee_File, Gitee_Release
from models.github import GitHub_Release, GitHub_Release_Asset

GITHUB_USER = getenv('GITHUB_USER')
GITHUB_REPO = getenv('GITHUB_REPO')

GITEE_USER = getenv('GITEE_USER')
GITEE_REPO = getenv('GITEE_REPO')
GITEE_RELEASE_REPO = getenv('GITEE_RELEASE_REPO}')

README_TITLE = getenv('README_TITLE') or  GITHUB_REPO
RELEASE_HISTORY_PREFIX = getenv('RELEASE_HISTORY_PREFIX') or '历史版本/'
RELEASE_LATEST_PERFIX = getenv('RELEASE_LATEST_PERFIX') or '最新版本/'

GITEE_ACCESS_TOKEN = getenv('GITEE_ACCESS_TOKEN')

DOWNLOAD_TASKS = 5
UPLOAD_TASKS = 1

BASE_DIR = path.split(path.realpath(__file__))[0]
DIST_DIR = path.join(BASE_DIR, 'dist')


async def get_github_release() -> List[GitHub_Release]:
    '''获取GitHub发行版信息'''
    async with ClientSession() as http:
        url = f'https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases'
        resp = await http.get(url)
        if resp.status == 200:
            raw = await resp.read()
            result = pydantic.parse_raw_as(List[GitHub_Release], raw)
            return result or []


async def get_github_release_latest() -> GitHub_Release:
    '''获取GitHub最新发行版的信息'''
    async with ClientSession() as http:
        url = f'https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest'
        resp = await http.get(url)
        if resp.status == 200:
            raw = await resp.read()
            result = pydantic.parse_raw_as(GitHub_Release, raw)
            return result


async def get_gitee_release() -> List[Gitee_Release]:
    '''获取Gitee发行版信息'''
    async with ClientSession() as http:
        url = f'https://gitee.com/api/v5/repos/{GITEE_USER}/{GITEE_REPO}/releases?access_token={GITEE_ACCESS_TOKEN}'
        resp = await http.get(url)
        if resp.status == 200:
            raw = await resp.read()
            result = pydantic.parse_raw_as(List[Gitee_Release], raw)
            return result


async def get_gitee_repo_folder(folder: str) -> List[Gitee_File]:
    '''获取Gitee仓库文件列表'''
    async with ClientSession() as http:
        url = f'https://gitee.com/api/v5/repos/{GITEE_USER}/{GITEE_RELEASE_REPO}/contents/{folder}?access_token={GITEE_ACCESS_TOKEN}'
        resp = await http.get(url)
        if resp.status == 200:
            raw = await resp.read()
            result = pydantic.parse_raw_as(List[Gitee_File], raw)
            return result


async def sync_folder_to_gitee(sem: Semaphore, remote_root_files: List[Gitee_File], latest_tag: str):
    '''同步文件夹到Gitee仓库'''

    async def create_file(http: ClientSession, local_path: str, remote_path: str):
        async with sem:
            url = f'https://gitee.com/api/v5/repos/{GITEE_USER}/{GITEE_RELEASE_REPO}/contents/{remote_path}?access_token={GITEE_ACCESS_TOKEN}'
            with open(local_path, 'rb') as f:
                content = f.read()

            payload = FormData({
                'content': b64encode(content).decode('utf-8'),
                'message': 'upload file',
            })
            resp = await http.post(url, data=payload)
            result = resp.status == 201 or resp.status == 200
            if result:
                print(f'创建文件 {remote_path} 成功')
            else:
                print(f'创建文件 {remote_path} 失败')

    async def update_file(http: ClientSession, local_path: str, remote_path: str, sha: str):
        async with sem:
            url = f'https://gitee.com/api/v5/repos/{GITEE_USER}/{GITEE_RELEASE_REPO}/contents/{remote_path}?access_token={GITEE_ACCESS_TOKEN}'
            with open(local_path, 'rb') as f:
                content = f.read()

            payload = FormData({
                'content': b64encode(content).decode('utf-8'),
                'sha': sha,
                'message': 'upload file',
            })
            resp = await http.put(url, data=payload)
            result = resp.status == 201 or resp.status == 200
            if result:
                print(f'更新文件 {remote_path} 成功')
            else:
                print(f'更新文件 {remote_path} 失败')

    # =====================================================================================
    local_root_folder = listdir(DIST_DIR)

    tasks = []
    async with ClientSession() as http:
        for folder_name in local_root_folder:
            folder_path = path.join(DIST_DIR, folder_name)
            if not path.isdir(folder_path):
                continue

            exist = False
            for file in remote_root_files:
                if file.name == folder_name and file.type == 'dir':
                    exist = True
                    break

            if exist:
                continue

            files_list = listdir(folder_path)
            remote_files = await get_gitee_repo_folder(f'/{folder_name}')

            for file_name in files_list:
                file_path = path.join(folder_path, file_name)
                if not path.isfile(file_path):
                    continue

                exist = False
                for file in remote_files:
                    if file.name == folder_name:
                        exist = True
                        break

                if exist:
                    tasks.append(
                        asyncio.create_task(
                            update_file(http, file_path,
                                        f'/{RELEASE_HISTORY_PREFIX}{folder_name}/{file_name}', file.sha)
                        )
                    )
                else:
                    tasks.append(
                        asyncio.create_task(
                            create_file(http, file_path,
                                        f'/{RELEASE_HISTORY_PREFIX}{folder_name}/{file_name}')
                        )
                    )

        if len(tasks) > 0:
            folder_path = path.join(DIST_DIR, latest_tag)
            if path.isdir(folder_path):
                files_list = listdir(folder_path)
                remote_files = await get_gitee_repo_folder(f'/{RELEASE_LATEST_PERFIX}')

                for file_name in files_list:
                    file_path = path.join(folder_path, file_name)
                    if not path.isfile(file_path):
                        continue

                    exist = False
                    for file in remote_files:
                        if file.name == folder_name:
                            exist = True
                            break

                    if exist:
                        tasks.append(
                            asyncio.create_task(
                                update_file(http, file_path,
                                            f'/{RELEASE_LATEST_PERFIX}{file_name}', file.sha)
                            )
                        )
                    else:
                        tasks.append(
                            asyncio.create_task(
                                create_file(http, file_path,
                                            f'/{RELEASE_LATEST_PERFIX}{file_name}')
                            )
                        )

        await asyncio.gather(*tasks)


def compare_releases(github_releases: List[GitHub_Release], gitee_releases: List[Gitee_Release]) -> List[GitHub_Release]:
    '''比较缺失的发行版'''
    diff = []

    for github in github_releases:
        tag = github.tag_name

        if not tag or len(github.assets) == 0:
            continue

        exists = False

        for gitee in gitee_releases:
            if gitee.tag_name == tag:
                exists = True
                break

        if not exists:
            diff.append(github)

    return diff


def compare_repo_files(github_releases: List[GitHub_Release], gitee_files: List[Gitee_File]) -> List[GitHub_Release]:
    '''比较发行版文件缺失'''
    diff = []

    for github in github_releases:
        tag = github.tag_name

        if not tag or len(github.assets) == 0:
            continue

        exists = False

        for file in gitee_files:
            if file.name == tag and file.type == 'dir':
                exists = True
                break

        if not exists:
            diff.append(github)

    return diff


async def download_release_assets(sem: Semaphore, github_release: GitHub_Release):
    '''下载发行版附件'''

    async def download_asset(http: ClientSession, asset: GitHub_Release_Asset, folder: str, tag: str):
        async with sem:
            url = asset.browser_download_url
            name = asset.name
            size = asset.size
            file_path = path.join(folder, name)

            resp = await http.get(url)
            if resp.status == 200:
                content = await resp.read()
                if size == len(content):
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    print(f'{tag} {name} 下载完成')
                else:
                    print(f'{tag} {name} 校验失败')
            else:
                print(f'{tag} {name} 下载失败')

    async with ClientSession() as http:
        tag_name = github_release.tag_name

        folder = path.join(DIST_DIR, tag_name)

        print(f'开始下载 {tag_name} -> {folder}')

        if not path.exists(folder):
            makedirs(folder)

        tasks = []

        for asset in github_release.assets:
            tasks.append(
                asyncio.create_task(
                    download_asset(http, asset, folder, tag_name)
                )
            )

        await asyncio.gather(*tasks)

        files = listdir(folder)
        if len(files) > 0:
            readme_path = path.join(folder, 'README.md')
            readme_lines = [x for x in github_release.body.replace(
                '\r', '\n').split('\n') if x]
            readme = '\n'.join(readme_lines)

            lines = [
                f'# {README_TITLE} v{tag_name}\n\n',
                f'## 更新说明\n\n',
                readme,
                '\n\n## 下载链接\n\n'
            ]

            for file in files:
                file_path = path.join(folder, file)
                if path.isfile(file_path) and file != 'README.md':
                    url = f'https://gitee.com/{GITEE_USER}/{GITEE_RELEASE_REPO}/raw/master/{RELEASE_HISTORY_PREFIX}{tag_name}/{file}'

                    lines.append(f'- [{file}]({url})\n')

            with open(readme_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        else:
            rmdir(folder)


async def main():
    # github
    print('获取GitHub发行版信息')
    github_releases = await get_github_release()

    # gitee
    print('获取Gitee仓库文件列表')
    remote_root_files = await get_gitee_repo_folder(f'/{RELEASE_HISTORY_PREFIX}')

    print('比较发行版差异')
    diff_releases = compare_repo_files(github_releases, remote_root_files)

    print('下载差异的发行版')
    sem = Semaphore(DOWNLOAD_TASKS)

    tasks = []
    for release in diff_releases:
        tasks.append(
            asyncio.create_task(
                download_release_assets(sem, release)
            )
        )

    await asyncio.gather(*tasks)

    latest_release = await get_github_release_latest()
    latest_tag = latest_release.tag_name

    print('上传发行版')
    sem = Semaphore(UPLOAD_TASKS)
    await sync_folder_to_gitee(sem, remote_root_files, latest_tag)


if __name__ == '__main__':
    asyncio.run(main(), debug=True)
