# URL Shortener Pro

基于 FastAPI + SQLAlchemy + Redis + Docker 的现代短链接服务，支持 JWT 鉴权、ORM 多表关联与 Redis 缓存加速。

## 功能特性

- **用户系统**：注册 / 登录获取 JWT Token（OAuth2 Password Flow + bcrypt 加密）
- **短链接管理**：创建短链接、查看个人短链接列表（SQLAlchemy 一对多关联）
- **Redis 缓存**：跳转请求优先查 Redis，命中则毫秒级返回；未命中回源数据库并自动写回缓存（TTL 1 小时）
- **容器化部署**：Docker Compose 一键启动（API + Redis），healthcheck 保证启动顺序
- **自动文档**：集成 Swagger UI 与 ReDoc，开箱即用
- **接口联调**：Postman 完整流程联调（注册 → 登录 → 创建 → 跳转）；**利用 JMeter 进行 50 线程/500 样本并发压测，验证了 Redis 缓存前后的性能差异**

## 技术栈

| 类别 | 技术                            |
|------|-------------------------------|
| 后端框架 | FastAPI                       |
| 数据库 ORM | SQLAlchemy 2.0                |
| 数据校验 | Pydantic V2                   |
| 缓存 | Redis 7                       |
| 鉴权 | JWT（python-jose）+ bcrypt      |
| 部署 | Docker / Docker Compose       |
| API 测试 | Postman / Swagger UI / Jmeter |

## 快速开始

### 前置要求

- 本地已安装并运行 **Docker Desktop**

### 一键启动

```bash
git clone https://github.com/txtangying/url-shortener-pro.git
cd url-shortener-pro
docker-compose up --build -d
```

### 访问服务

| 服务 | 地址 |
|------|------|
| API 文档（Swagger） | http://127.0.0.1:8000/docs |
| API 文档（ReDoc） | http://127.0.0.1:8000/redoc |
| 短链接跳转 | http://127.0.0.1:8000/{short_code} |

## 接口一览

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|:----:|
| POST | `/register` | 用户注册 | 否 |
| POST | `/token` | 登录获取 JWT Token | 否 |
| POST | `/urls/` | 创建短链接 | 是 |
| GET | `/urls/` | 查看个人短链接列表 | 是 |
| GET | `/{short_code}` | 短链接 302 跳转 | 否 |

## API 使用示例

### 1. 注册

`POST /register`

```json
{
  "username": "test01",
  "email": "test01@example.com",
  "password": "123456"
}
```

### 2. 登录获取 Token

`POST /token`（form-data：username、password）

返回示例：

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

### 3. 创建短链接（需 Authorization Header）

`POST /urls/`

- Headers：`Authorization: Bearer <access_token>`
- Body：

```json
{
  "original_url": "https://www.baidu.com"
}
```

> 提示：在 Swagger UI 顶部点击 **Authorize**，输入用户名与密码即可自动获取并在后续请求中携带 Token，无需手动复制 Header。

### 4. 访问短链接

浏览器直接访问 `http://127.0.0.1:8000/{short_code}`，服务将 **302 跳转** 到目标网址。

## 项目结构

```
.
├── main.py              # 应用入口、API 路由、数据库模型、鉴权逻辑
├── requirements.txt     # Python 依赖清单
├── docker-compose.yml   # Docker 编排配置（含健康检查）
├── Dockerfile           # API 服务镜像构建
├── test.db              # SQLite 数据库文件（自动生成）
└── README.md
```

## 设计亮点

- **缓存策略**：Redis GET 优先 → 未命中查 SQLite → SETEX 写回缓存（TTL 3600s），有效降低数据库压力
- **依赖注入**：FastAPI `Depends` 实现数据库连接管理与 JWT 鉴权解耦，代码清晰可测
- **容器编排**：`healthcheck` + `depends_on: condition: service_healthy` 确保 Redis 就绪后 API 才启动，避免启动竞态
- **安全存储**：bcrypt 原生加密密码，JWT 无状态鉴权，Token 过期机制

## 📄 开源协议
本项目遵循 **MIT License** 协议。欢迎 Fork 和二次开发。