from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import bcrypt  # 改为原生 bcrypt
import random
import string
import redis
app = FastAPI()
import os
# 默认找名为 "redis" 的容器，如果在本地跑才用 127.0.0.1
redis_host = os.getenv("REDIS_HOST", "redis")
#redis_client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)

cache = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)

# --- 1. 配置信息 ---
SECRET_KEY = "your-secret-key-here-change-it-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

# --- 2. 初始化设置 ---
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ✅ 导入下面这两行是关键！
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# 初始化 FastAPI
app = FastAPI(title="短链接生成器 - 功能1：JWT鉴权与ORM关联")


# --- 3. 数据库模型 (ORM 关联) ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    urls = relationship("URL", back_populates="owner")


class URL(Base):
    __tablename__ = "urls"
    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(String, index=True)
    short_code = Column(String, unique=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="urls")


# 创建数据库表
Base.metadata.create_all(bind=engine)


# --- 4. Pydantic 数据模型 (数据校验) ---
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    # ✅ 修正为 Pydantic v2 的写法，避免警告
    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str


class URLCreate(BaseModel):
    original_url: str


class URLOut(BaseModel):
    id: int
    original_url: str
    short_code: str
    model_config = {"from_attributes": True}


# --- 5. 工具函数 ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ✅ 彻底替换掉 passlib 的代码，使用原生 bcrypt
def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        # ✅ 修复 Python 3.14 中 datetime.utcnow() 废弃的告警
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# ✅ 修复 get_current_user 的依赖项，现在它可以从 header 提取 Bearer Token 了
async def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


# --- 6. API 接口 ---

# 1. 用户注册
@app.post("/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# 2. 用户登录 (获取 JWT Token)
@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

# 3. 创建短链接 (需要登录鉴权)
@app.post("/urls/", response_model=URLOut)
def create_url(url: URLCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 生成一个唯一的短码（可以加个循环，如果短码重复则重新生成）
    short_code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

    # 为了避免冲突，实际生产环境会查一下数据库有没有这个短码，如果有就重新生成，这里先忽略。
    db_url = URL(original_url=url.original_url,short_code=short_code, owner_id=current_user.id)
    db.add(db_url)
    db.commit()
    db.refresh(db_url)
    return db_url

# 4. 查看我的短链接 (需要登录鉴权，体现 ORM 关联)
@app.get("/my-urls/", response_model=List[URLOut])
def read_my_urls(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    urls = db.query(URL).filter(URL.owner_id == current_user.id).all()
    return urls

# 5. 根路径
@app.get("/")
def read_root():
    return {"message": "欢迎使用短链接服务，请先注册并登录获取 Token"}


# 6. 重定向短链接（带 Redis 缓存）
@app.get("/{short_code}")
def redirect_url(short_code: str, db: Session = Depends(get_db)):
    # 1. 先查 Redis 缓存
    cached_url = cache.get(short_code)
    if cached_url:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=cached_url)

    # 2. Redis 没有，查数据库
    db_url = db.query(URL).filter(URL.short_code == short_code).first()
    if not db_url:
        raise HTTPException(status_code=404, detail="短链接不存在")

    # 3. 写入 Redis 缓存
    cache.setex(short_code, 3600, db_url.original_url)

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=db_url.original_url)