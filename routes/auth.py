from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User

# Создаем Blueprint для аутентификации
auth_bp = Blueprint('auth', __name__)

# Маршру для логина и получения токена
@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()  # Получаем данные из тела запроса
    username = data.get('username')
    password = data.get('password')
    
    # Проверяем, что оба поля (username и password) переданы
    if not username or not password:
        return jsonify({'error': 'Требуется имя пользователя и пароль'}), 400
    
    # Ищем пользователя в базе данных
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'Неверные учетные данные'}), 401  # Пользователь не найден
    
    # Проверяем, что хэш пароля совпадает
    if not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Неверные учетные данные'}), 401  # Пароль неверный
    
    # Создаем JWT токен для авторизованного пользователя
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={'role': user.role, 'username': user.username}
    )
    
    # Возвращаем токен и данные пользователя
    return jsonify({
        'access_token': access_token,
        'user': {
            'id': user.id,
            'username': user.username,
            'role': user.role
        }
    }), 200


# Маршрут для регистрации нового пользователя
@auth_bp.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()  # Получаем данные из запроса
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'STUDENT')  # По умолчанию роль 'STUDENT'
    
    # Проверяем, что имя пользователя и пароль переданы
    if not username or not password:
        return jsonify({'error': 'Требуется имя пользователя и пароль'}), 400
    
    # Проверяем, что пользователь с таким именем не существует
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Пользователь уже существует'}), 400
    
    # Проверяем корректность роли
    if role not in ['STUDENT', 'OPERATOR', 'ADMIN']:
        return jsonify({'error': 'Недопустимая роль'}), 400
    
    # Хэшируем пароль перед сохранением в базе данных
    hashed_password = generate_password_hash(password)
    
    # Создаем нового пользователя
    user = User(username=username, password_hash=hashed_password, role=role)
    
    # Сохраняем пользователя в базе данных
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'message': 'Пользователь создан успешно', 'user_id': user.id}), 201


# Маршрут для получения данных о текущем пользователе (только для авторизованных)
@auth_bp.route('/api/profile', methods=['GET'])
@jwt_required()  # Требуется авторизация через JWT
def profile():
    user_id = int(get_jwt_identity())  # Получаем идентификатор текущего пользователя из токена
    user = User.query.get(user_id)  # Ищем пользователя по ID
    
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404  # Если пользователь не найден
    
    # Возвращаем информацию о пользователе
    return jsonify({
        'id': user.id,
        'username': user.username,
        'role': user.role,
        'created_at': user.created_at.isoformat()
    }), 200
