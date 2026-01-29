from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Service, Window, Schedule, User

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/api/admin/services', methods=['GET'])
@jwt_required()
def get_services():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role != 'ADMIN':
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    services = Service.query.all()
    result = []
    
    for service in services:
        result.append({
            'id': service.id,
            'name': service.name,
            'avg_service_time_min': service.avg_service_time_min,
            'is_active': service.is_active
        })
    
    return jsonify({'services': result}), 200

@admin_bp.route('/api/admin/services', methods=['POST'])
@jwt_required()
def create_service():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role != 'ADMIN':
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    data = request.get_json()
    name = data.get('name')
    avg_time = data.get('avg_service_time_min', 10)
    
    if not name:
        return jsonify({'error': 'Требуется название услуги'}), 400
    
    service = Service(name=name, avg_service_time_min=avg_time)
    db.session.add(service)
    db.session.commit()
    
    return jsonify({
        'message': 'Услуга создана',
        'service': {
            'id': service.id,
            'name': service.name,
            'avg_service_time_min': service.avg_service_time_min
        }
    }), 201

@admin_bp.route('/api/admin/services/<int:service_id>', methods=['PUT'])
@jwt_required()
def update_service(service_id):
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role != 'ADMIN':
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    service = Service.query.get(service_id)
    if not service:
        return jsonify({'error': 'Услуга не найдена'}), 404
    
    data = request.get_json()
    
    if 'name' in data:
        service.name = data['name']
    if 'avg_service_time_min' in data:
        service.avg_service_time_min = data['avg_service_time_min']
    if 'is_active' in data:
        service.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Услуга обновлена',
        'service': {
            'id': service.id,
            'name': service.name,
            'avg_service_time_min': service.avg_service_time_min,
            'is_active': service.is_active
        }
    }), 200

@admin_bp.route('/api/admin/windows', methods=['GET'])
@jwt_required()
def get_windows():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role != 'ADMIN':
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    windows = Window.query.all()
    result = []
    
    for window in windows:
        result.append({
            'id': window.id,
            'name': window.name
        })
    
    return jsonify({'windows': result}), 200

@admin_bp.route('/api/admin/schedule', methods=['GET'])
@jwt_required()
def get_schedule():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role != 'ADMIN':
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    schedule = Schedule.query.all()
    result = []
    
    for item in schedule:
        result.append({
            'id': item.id,
            'day_of_week': item.day_of_week,
            'time_from': item.time_from.strftime('%H:%M'),
            'time_to': item.time_to.strftime('%H:%M')
        })
    
    return jsonify({'schedule': result}), 200