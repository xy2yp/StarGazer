# Dockerfile
# 使用官方的 Python 基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制 requirements.txt
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 将前端的静态资源复制到容器内的 /app/static/ 目录
COPY frontend/www/ ./app/static/

# 将后端的应用代码复制到工作目录
COPY backend/app/ ./app/

# 暴露后端服务监听的端口
EXPOSE 8000

# 启动应用的命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
