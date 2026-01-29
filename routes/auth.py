from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Требуется имя пользователя и пароль'}), 400
    
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Неверные учетные данные'}), 401
    
    # Создаем JWT токен
    access_token = create_access_token(
        identity=user.id,
        additional_claims={'role': user.role, 'username': user.username}
    )
    
    return jsonify({
        'access_token': access_token,
        'user': {
            'id': user.id,
            'username': user.username,
            'role': user.role
        }
    }), 200

@auth_bp.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'STUDENT')
    
    if not username or not password:
        return jsonify({'error': 'Требуется имя пользователя и пароль'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Пользователь уже существует'}), 400
    
    if role not in ['STUDENT', 'OPERATOR', 'ADMIN']:
        return jsonify({'error': 'Недопустимая роль'}), 400
    
    hashed_password = generate_password_hash(password)
    user = User(username=username, password_hash=hashed_password, role=role)
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'message': 'Пользователь создан успешно', 'user_id': user.id}), 201

@auth_bp.route('/api/profile', methods=['GET'])
@jwt_required()
def profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'role': user.role,
        'created_at': user.created_at.isoformat()
    }), 200