# StarGazer 星眸
## An Open-Source, Elegant, and Efficient GitHub Stars Management Tool.
[中文](./README.md)

Have you ever found yourself:
 - Starring a repository on a whim, then pulling your hair out trying to find it later?
 - Wanting to find a repository, but your mind goes blank and you just can't recall its name?
 - Remembering what a repository is for, but not its Repo name?
 - Finally recalling a few keywords, only to get a mess of search results?
 - Wanting to follow up on repository updates, but always missing important releases?
 - Feeling the urge to categorize your starred projects, but not knowing where to begin?
 - Having some thoughts on a project and wishing you could jot them down instantly?
 - Searching for a good Star management tool, but never finding one that feels just right?

So have I! ~~So I decided to build one myself.~~

**StarGazer** helps you manage your GitHub Stars with elegance and efficiency. Say goodbye to the frustration of getting lost among countless stars and rediscover the treasures you've collected.

<img width="1100" height="647" alt="image" src="https://github.com/user-attachments/assets/52997f8a-9018-4f51-91a6-e8410387ef25" />
<img width="1323" height="543" alt="image" src="https://github.com/user-attachments/assets/09e77f0e-55bb-40a9-9047-bda2184f2450" />

## ✨ Features
- **OAuth Login Support**: Securely and conveniently log in using your GitHub account.
- **Auto Sync**: Automatically syncs all your GitHub Stars.
- **Push Notifications**: Get update notifications through multiple channels (Bark, Gotify, ServerChan, Webhook).
- **Group Management**: Add custom tags to your starred projects and use drag-and-drop sorting for flexible organization.
- **Alias Support**: Add aliases to projects for precise locating, so you don't have to remember those long Repo names.
- **Note-Taking**: Jot down your ideas and key information to keep learning and improving.
- **Smart Search**: Fuzzy search by repository name, description, alias, tags, language, and more.
- **View Switching**: Seamlessly switch between list and card views.
- **Flexible Sorting**: Sort by bookmark time, star count, project name, and more.
- **Responsive Design**: Enjoy a great experience on both desktop and mobile devices.
- **Open Source & Self-Hosted**: Completely open source, allowing you to easily deploy it on your own server.
- **Data Persistence**: All your data (including tags, notes, etc.) is stored locally, giving you full control.
- **i18n Support**: Available in Chinese and English. Contributions for other languages are welcome.
- **And Many Easter Eggs**: Discover the little thoughtful touches hidden by a developer.

## 🚀 Quick Start

Using Docker Compose is the recommended way for a quick deployment.

### Step 1: Get GitHub OAuth App Credentials

Before deploying, you need to obtain a `Client ID` and `Client Secret` from GitHub.

1.  Go to GitHub's [Developer settings](https://github.com/settings/developers) page.
2.  Click **"New OAuth App"** to create a new application.
3.  Fill in the application information:
    -   **Application name**: Any name you like, e.g., `StarGazer`.
    -   **Homepage URL**: The homepage of your application. Fill in the domain or IP address where you will deploy it, e.g., `http://your-domain.com` or `http://192.168.1.100:8000`.
    -   **Authorization callback URL**: This **must** be set to `http://<your-domain-or-IP>:<port>/auth/callback`. For example, `http://your-domain.com/auth/callback` or `http://192.168.1.100:8000/auth/callback`.
4.  Click **"Register application"**. On the next page, you will see the `Client ID`. Click **"Generate a new client secret"** to create the `Client Secret`. Be sure to **copy and save** both values immediately.

### Step 2: Deploy and Configure the Project

#### Method 1: Deploy with Pre-built Image (Recommended)
Using the pre-built image is more convenient.
1.  **Pull the Docker image**
    ```bash
	docker pull xy2yp/stargazer:latest
	```
2. **Modify the `docker-compose.yml` file**
   ```yaml
   version: '3.8'
   services:
     stargazer:
       # Use the pre-built image
       image: xy2yp/stargazer:latest
       container_name: stargazer
       restart: unless-stopped
       ports:
         # Format: <host_port>:<container_port>
         - "8000:8000"
       volumes:
         - ./data:/data
       environment:
         # --- Required ---
         # GitHub OAuth App Configuration
         # Create it in GitHub -> Settings -> Developer settings -> OAuth Apps
         # The callback URL must be set to: http://<your_server_ip_or_domain>:<host_port>/auth/callback
         - GITHUB_CLIENT_ID=<YOUR_GITHUB_CLIENT_ID>
         - GITHUB_CLIENT_SECRET=<YOUR_GITHUB_CLIENT_SECRET>

         # A secret key for encrypting sessions and sensitive data
         # Must be a secure random string, at least 32 characters long. Use `openssl rand -hex 32` to generate one.
         - SECRET_KEY=<YOUR_SECURE_RANDOM_STRING>

         # --- Optional ---
         # Debug mode (should be False in production)
         - DEBUG=False

         # Cookie max age in days, defaults to 30
         - COOKIE_MAX_AGE_DAYS=30

         # If the application is deployed behind a reverse proxy, set your domain
         # Example: - DOMAIN=stargazer.example.com
         - DOMAIN=

         # Timezone setting
         - TZ=Asia/Shanghai

         # Network proxy settings
         # - HTTP_PROXY=http://127.0.0.1:7890
         # - HTTPS_PROXY=http://127.0.0.1:7890
         - HTTP_PROXY=
         - HTTPS_PROXY=
   ```

#### Method 2: Build from Source
Choose this method if you are a developer or wish to modify the code before deployment.
1.  **Clone the source code**
    ```bash
    git clone https://github.com/xy2yp/stargazer.git
    cd stargazer
    ```
2.  **Create and modify the `docker-compose.yml` file**
    Copy `docker-compose.build.yml.example` to `docker-compose.yml`:
    ```bash
    cp docker-compose.build.yml.example docker-compose.yml
    ```
    Then, set the environment variables as described in Method 1.

### Step 3: Start the Service

Use Docker Compose to start the application with a single command:

```bash
docker-compose up -d
```

### Step 4: Access the Application

Deployment successful! Start managing your GitHub Stars with StarGazer!
**Please note that StarGazer is designed for personal, single-user use.**
**Do not use multiple accounts or share the same instance with others, as this will lead to user data confusion and overwriting.**
**If multi-user support is needed, please deploy multiple instances.**

## 🌳 File Tree

```
StarGazer/
├── backend/                                  # Backend FastAPI Application
│   ├── app/                                  # Core application code
│   │   ├── main.py                           # [Entrypoint] FastAPI main entrypoint, handles lifecycle events
│   │   ├── config.py                         # [Config] Pydantic configuration management, loaded from environment variables
│   │   ├── db.py                             # [Database] Database session management
│   │   ├── models.py                         # [Data Models] SQLModel database models
│   │   ├── schemas.py                        # [Data Structures] Pydantic API data structures (request/response bodies)
│   │   ├── exceptions.py                     # [Exception Handling] Custom exception classes
│   │   ├── version.py                        # [Version Info] Application version number
│   │   ├── api/                              # API routing modules
│   │   │   ├── auth.py                       # [Auth] Handles GitHub OAuth2 authentication flow
│   │   │   ├── dependencies.py               # [Dependency Injection] FastAPI dependencies (e.g., user authentication)
│   │   │   ├── stars.py                      # [Core API] API endpoints for starred repository data (query, sync, update)
│   │   │   ├── users.py                      # [User API] API endpoints for user information
│   │   │   ├── tags.py                       # [Tags API] API endpoints for tag management
│   │   │   ├── settings.py                   # [Settings API] API endpoints for application settings
│   │   │   └── version.py                    # [Version API] API endpoint to get the application version
│   │   ├── core/                             # Core business logic and services
│   │   │   ├── notifiers/                    # Push notification service modules
│   │   │   │   ├── bark.py                   # Bark push implementation
│   │   │   │   ├── base.py                   # Abstract base class for notification services
│   │   │   │   ├── factory.py                # Notification service factory for creating specific instances
│   │   │   │   ├── gotify.py                 # Gotify push implementation
│   │   │   │   ├── message.py                # Localized notification message generator
│   │   │   │   ├── serverchan.py             # ServerChan push implementation
│   │   │   │   └── webhook.py                # Generic Webhook push implementation
│   │   │   ├── github.py                     # GitHub API client, encapsulates API requests
│   │   │   ├── scheduler.py                  # APScheduler for background scheduled synchronization tasks
│   │   │   ├── security.py                   # Encryption/decryption service (for tokens, etc.)
│   │   │   ├── settings_service.py           # Service for reading/writing application settings
│   │   │   ├── sync_service.py               # Core data synchronization service
│   │   │   └── tags_service.py               # CRUD service for tags
│   │   ├── locales/                          # Backend i18n localization files
│   │   │   ├── en.json                       # English
│   │   │   └── zh.json                       # Chinese
│   ├── Dockerfile                            # Dockerfile for the backend service
│   └── requirements.txt                      # Python dependency list
├── frontend/                                 # Frontend Vanilla JavaScript Application
│   └── www/                                  # Web server root directory
│       ├── assets/                           # Static assets
│       │   ├── icons/                        # PWA and website icons
│       │   ├── images/                       # Image resources (e.g., donation QR codes)
│       │   └── libs/                         # Third-party JavaScript libraries
│       ├── css/                              # CSS stylesheets
│       │   ├── pico.min.css                  # Pico.css framework
│       │   └── style.css                     # Custom styles
│       ├── js/                               # Custom JavaScript logic
│       │   ├── api.js                        # Frontend API client
│       │   ├── i18n.js                       # i18next initialization and configuration
│       │   ├── main.js                       # Main application logic and controller
│       │   └── ui.js                         # DOM manipulation and UI update logic
│       ├── locales/                          # Frontend i18n localization files
│       │   ├── en.json                       # English
│       │   └── zh.json                       # Chinese
│       ├── index.html                        # Single Page Application main entry HTML
│       └── manifest.json                     # PWA (Progressive Web App) configuration file
├── .env.example                              # Environment variable example file
├── docker-compose.pull.yml.example           # Docker Compose example file (for pulling image)
├── docker-compose.build.yml.example          # Docker Compose example file (for self-building)
├── LICENSE                                   # Project license
├── README.md                                 # Project documentation (Chinese)
└── README_en.md                              # Project documentation (English)
```

## 📊 Telemetry

To better understand and improve StarGazer, the application sends a **Single**, **Anonymous** telemetry event upon startup.

- **What do we collect?** Only the current deployed **version** of the application.
- **What do we NOT collect?** The telemetry is completely anonymous.We **Do Not & Will Not** collect any personally identifiable information (PII), your GitHub data, API keys, IP addresses, or any other sensitive information. 
- **How to disable it?** If you prefer not to send this information, you can completely disable it by setting an environment variable in your `docker-compose.yml` file:
  ```yaml
  environment:
    - DISABLE_TELEMETRY=True
  ```

## 🛠️ Tech Stack

-   **Backend**: FastAPI
-   **Frontend**: JavaScript
-   **Database**: SQLite
-   **Deployment**: Docker

## 🤝 Contributing

Contributions of all forms are welcome! If you have any ideas, suggestions, or have found a bug, please feel free to submit an Issue or Pull Request.

## ❤️ Donate

If you find this project helpful, consider buying me a coffee to support my work!

## 📄 License

This project is open-sourced under the [GPLv3 License](./LICENSE).
