
# StarGazer -- 星眸 
## 一个开源、优雅、高效的 GitHub Stars 管理工具。
[English](./README_en.md)

你有没有试过：
 - 随手Star的仓库，再找的时候找到头秃...
 - 想要找一个仓库，却原地失忆死活想不起仓库名是什么...
 - 只记得仓库的用途却想不起他的英文名是什么...
 - 好不容易想起几个关键字了，搜索却是一坨...
 - 想快速跟进仓库更新，却总是错过重要的 Release...
 - 想给Star的项目分个类，却无从下手...
 - 对某个项目有些想法，希望能够随手记下...
 - 想找个好用的Star仓库管理项目，却没找到顺手的...

我也是！~~所以我自己肝了一个出来~~

**StarGazer -- 星眸** 帮助您优雅、高效地管理 GitHub Stars。告别在 N 个 Star 中迷失的烦恼，重新发现您收藏的宝藏。

<img width="1100" height="647" alt="image" src="https://github.com/user-attachments/assets/52997f8a-9018-4f51-91a6-e8410387ef25" />

<img width="1323" height="543" alt="image" src="https://github.com/user-attachments/assets/09e77f0e-55bb-40a9-9047-bda2184f2450" />

## ✨ 功能特性
- **支持授权登录**：安全、便捷地使用您的 GitHub 账户授权登录
- **支持自动同步**：自动同步您所有的 GitHub Stars，无需手动干预
- **支持消息推送**：多渠道（Bark, Gotify, Server酱, Webhook）推送更新消息
- **支持分组管理**：为您的 Star 项目添加自定义标签，并支持拖拽排序，实现灵活的分组管理
- **支持设置别名**：为项目添加备注名，精准定位，不用记那个长长的英文了
- **支持撰写笔记**：记录您的想法和关键信息，天天向上
- **支持智能搜索**：按仓库名称、描述、备注、标签、语言等进行模糊搜索
- **支持视图切换**：列表/卡片视图，无缝切换
- **支持排序切换**：按收藏时间、Star 数量、项目名称等进行排序
- **支持响应式设计**：在桌面和移动设备上均有良好体验
- **开源与自托管**：完全开源，您可以轻松地将其部署在自己的服务器上
- **数据持久化**：所有数据（包括标签、备注等）都存储在本地，由您完全掌控
- **支持 i18n**：中文和英文界面，欢迎提供其他语言文档
- **还有很多彩蛋**：有很多理工男小心思，等你发现

## 🚀 快速开始

推荐使用 Docker Compose 进行快速部署。

### 第 1 步：获取 GitHub OAuth App 凭证

在部署之前，您需要先从 GitHub 获取 `Client ID` 和 `Client Secret`。

1.  前往 GitHub 的[开发者设置页面](https://github.com/settings/developers)。
2.  点击 **"New OAuth App"** 创建一个新的应用。
3.  填写应用信息：
    -   **Application name**：应用名称，可以随意填写，例如 `StarGazer`。
    -   **Homepage URL**：您的应用主页，填写您将要部署的域名或 IP 地址，例如 `http://your-domain.com` 或 `http://192.168.1.100:8000`。
    -   **Authorization callback URL**：必须填写为 `http://<你的域名或IP>:<端口>/auth/callback`。例如 `http://your-domain.com/auth/callback` 或 `http://192.168.1.100:8000/auth/callback`。
4.  点击 **"Register application"**。在下一个页面，您将看到 `Client ID`。点击 **"Generate a new client secret"** 来生成 `Client Secret`。请务必**立即复制并保存**这两个值。

### 第 2 步：项目部署及配置

#### 方式一：使用预构建镜像部署（推荐）
推荐使用预构建镜像直接部署，更方便。
1.  **拉取Docker镜像**
    ```bash
	docker pull xy2yp/stargazer:latest
	```
2. **修改 `docker-compose.yml` 文件**
   ```bash
   version: '3.8'
   services:
   stargazer:
   # 使用预构建镜像
   image: xy2yp/stargazer:latest
    container_name: stargazer
    restart: unless-stopped
    ports:
      # 格式: <主机端口>:<容器端口>
      - "8000:8000"
    volumes:
      - ./data:/data
    environment:
      # --- 必填项 ---
      # GitHub OAuth App 配置
      # 在 GitHub -> Settings -> Developer settings -> OAuth Apps 中创建
      # 回调 URL 必须设置为: http://<你的服务器IP或域名>:<主机端口>/auth/callback
      - GITHUB_CLIENT_ID=<YOUR_GITHUB_CLIENT_ID>
      - GITHUB_CLIENT_SECRET=<YOUR_GITHUB_CLIENT_SECRET>

      # 用于加密会话和敏感数据的密钥
      # 必须是一个安全的随机字符串，建议不低于32位，可使用 `openssl rand -hex 32` 生成
      - SECRET_KEY=<YOUR_SECURE_RANDOM_STRING>

      # --- 可选项 ---
      # 调试模式 (生产环境应设为 False)
      - DEBUG=False

      # Cookie 有效期（天），默认为 30
      - COOKIE_MAX_AGE_DAYS=30

      # 如果应用部署在反向代理之后，请设置你的域名
      # 例如: - DOMAIN=stargazer.example.com
      - DOMAIN=

      # 时区设置
      - TZ=Asia/Shanghai

      # 网络代理设置 
      # - HTTP_PROXY=http://127.0.0.1:7890
      # - HTTPS_PROXY=http://127.0.0.1:7890
      - HTTP_PROXY=
      - HTTPS_PROXY=
   ```

#### 方式二：自行构建镜像部署
如果您是开发者，或者希望在部署前对代码进行修改，可以选择此方式。
1.  **克隆源码**
    ```bash
    git clone https://github.com/xy2yp/stargazer.git
    cd stargazer
    ```
2.  **创建并修改 `docker-compose.yml` 文件**
    将 `docker-compose.build.yml.example` 文件复制为 `docker-compose.yml`：
    ```bash
    cp docker-compose.build.yml.example docker-compose.yml
    ```
    参照方式一设置环境变量。

### 第 3 步：启动服务

使用 Docker Compose 一键启动应用：

```bash
docker-compose up -d
```

### 第 4 步：访问应用

部署成功！开始使用星眸管理您的 GitHub Stars 吧！

## 🌳 文件树

```
StarGazer/
├── backend/                                  # 后端 FastAPI 应用
│   ├── app/                                  # 应用核心代码
│   │   ├── main.py                           # 【入口】FastAPI 应用主入口，处理生命周期事件
│   │   ├── config.py                         # 【配置】Pydantic 配置管理，从环境变量加载
│   │   ├── db.py                             # 【数据库】数据库会话管理
│   │   ├── models.py                         # 【数据模型】SQLModel 数据库模型
│   │   ├── schemas.py                        # 【数据结构】Pydantic API 数据结构 (请求体/响应体)
│   │   ├── exceptions.py                     # 【异常处理】自定义异常类
│   │   ├── version.py                        # 【版本信息】应用版本号
│   │   ├── api/                              # API 路由模块
│   │   │   ├── auth.py                       # 【认证】处理 GitHub OAuth2 认证流程
│   │   │   ├── dependencies.py               # 【依赖注入】FastAPI 依赖项 (如用户身份验证)
│   │   │   ├── stars.py                      # 【核心API】星标仓库数据相关的 API 端点 (查询、同步、更新)
│   │   │   ├── users.py                      # 【用户API】用户信息相关的 API 端点
│   │   │   ├── tags.py                       # 【标签API】标签管理相关的 API 端点
│   │   │   ├── settings.py                   # 【设置API】应用设置相关的 API 端点
│   │   │   └── version.py                    # 【版本API】获取应用版本的 API 端点
│   │   ├── core/                             # 核心业务逻辑和服务
│   │   │   ├── notifiers/                    # 推送通知服务模块
│   │   │   │   ├── bark.py                   # Bark 推送实现
│   │   │   │   ├── base.py                   # 通知服务的抽象基类
│   │   │   │   ├── factory.py                # 通知服务工厂，用于创建具体实例
│   │   │   │   ├── gotify.py                 # Gotify 推送实现
│   │   │   │   ├── message.py                # 本地化通知消息生成器
│   │   │   │   ├── serverchan.py             # Server酱 推送实现
│   │   │   │   └── webhook.py                # 通用 Webhook 推送实现
│   │   │   ├── github.py                     # GitHub API 客户端，封装了 API 请求
│   │   │   ├── scheduler.py                  # APScheduler 后台定时同步任务
│   │   │   ├── security.py                   # 加密/解密服务 (用于 token 等)
│   │   │   ├── settings_service.py           # 应用设置的读写服务
│   │   │   ├── sync_service.py               # 核心数据同步服务
│   │   │   └── tags_service.py               # 标签的增删改查服务
│   │   ├── locales/                          # 后端 i18n 本地化语言文件
│   │   │   ├── en.json                       # 英文
│   │   │   └── zh.json                       # 中文
│   ├── Dockerfile                            # 后端服务的 Dockerfile
│   └── requirements.txt                      # Python 依赖项列表
├── frontend/                                 # 前端 Vanilla JavaScript 应用
│   └── www/                                  # Web 服务根目录
│       ├── assets/                           # 静态资源
│       │   ├── icons/                        # PWA 和网站图标
│       │   ├── images/                       # 图片资源 (如捐赠二维码)
│       │   └── libs/                         # 第三方 JavaScript 库
│       ├── css/                              # CSS 样式文件
│       │   ├── pico.min.css                  # Pico.css 框架
│       │   └── style.css                     # 自定义样式
│       ├── js/                               # 自定义 JavaScript 逻辑
│       │   ├── api.js                        # 前端 API 客户端
│       │   ├── i18n.js                       # i18next 初始化和配置
│       │   ├── main.js                       # 主应用逻辑和控制器
│       │   └── ui.js                         # DOM 操作和 UI 更新逻辑
│       ├── locales/                          # 前端 i18n 本地化语言文件
│       │   ├── en.json                       # 英文
│       │   └── zh.json                       # 中文
│       ├── index.html                        # 单页应用主入口 HTML
│       └── manifest.json                     # PWA (渐进式 Web 应用) 配置文件
├── .env.example                              # 环境变量示例文件
├── docker-compose.pull.yml.example           # Docker Compose 示例文件（拉取镜像）
├── docker-compose.build.yml.example          # Docker Compose 示例文件（自构建）
├── LICENSE                                   # 项目许可证
├── README.md                                 # 项目说明文档 (中文)
└── README_en.md                              # 项目说明文档 (英文)
```

## 🛠️ 技术栈

-   **后端**: FastAPI
-   **前端**: JavaScript
-   **数据库**: SQLite
-   **部署**: Docker

## 🤝 贡献

欢迎各种形式的贡献！如果您有任何想法、建议或发现了 Bug，请随时提交 Issue 或 Pull Request。

## ❤️ 捐赠

如果您觉得这个项目对您有帮助，不妨请我喝一杯咖啡~~支持我接着肝！

## 📄 许可证

本项目基于 [GPLv3 License](./LICENSE) 开源。
