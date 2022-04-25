# Sync_Release

> 同步 Github Release 到 Gitee 仓库

> 本来是计划同步到码云的 Release 的, 但是码云的 Release 上传没有给 API, 只能传到另一个仓库里曲线救国了

## 使用方法

需要 Python3.7 以上版本

### 环境变量说明

| 环境变量名             | 说明                                             | 必须 |
| ---------------------- | ------------------------------------------------ | ---- |
| GITHUB_USER            | GitHub 用户名                                    | ✔️   |
| GITHUB_REPO            | 需要同步的 GitHub 仓库名                         | ✔️   |
| GITEE_USER             | 码云用户名                                       | ✔️   |
| GITEE_RELEASE_REPO     | 存放 Release 文件的码云仓库名                    | ✔️   |
| GITEE_ACCESS_TOKEN     | 码云 AccessToken                                 | ✔️   |
| README_TITLE           | README 标题前缀                                  |      |
| RELEASE_HISTORY_PREFIX | 旧 Release 上传位置前缀 (默认为 "历史版本/")     |      |
| RELEASE_LATEST_PERFIX  | 最新的 Release 上传位置前缀 (默认为 "最新版本/") |      |
