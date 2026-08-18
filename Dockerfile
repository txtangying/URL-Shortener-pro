# 使用官方 Python 3.9 镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 将依赖文件复制进去并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 将项目代码复制进去
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]