from datetime import timedelta

class Config:
    SECRET_KEY = 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:123456@localhost:5432/queue_system?client_encoding=utf8&sslmode=disable'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = 'jwt-secret-key-change'  # Секретный ключ для JWT
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)  # Время жизни токена (1 час)
