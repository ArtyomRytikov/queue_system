from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Ticket, User, EventLog, Window
from utils.queue_logic import get_next_ticket
from datetime import datetime

operator_bp = Blueprint('operator', __name__)

@operator_bp.route('/api/operator/next', methods=['POST'])
@jwt_required()
def call_next():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    # Проверяем роль
    if user.role not in ['OPERATOR', 'ADMIN']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    data = request.get_json()
    window_id = data.get('window_id', 1)
    
    window = Window.query.get(window_id)
    if not window:
        return jsonify({'error': 'Окно не найдено'}), 404
    
    # Получаем следующий талон
    next_ticket = get_next_ticket(user_id, window_id)
    
    if not next_ticket:
        return jsonify({'message': 'Нет талонов в очереди'}), 404
    
    return jsonify({
        'ticket': {
            'id': next_ticket.id,
            'ticket_number': next_ticket.ticket_number,
            'service_name': next_ticket.service.name,
            'created_at': next_ticket.created_at.isoformat()
        },
        'window': {
            'id': window.id,
            'name': window.name
        },
        'operator': {
            'id': user.id,
            'username': user.username
        }
    }), 200

@operator_bp.route('/api/operator/tickets/<int:ticket_id>/served', methods=['POST'])
@jwt_required()
def mark_served(ticket_id):
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role not in ['OPERATOR', 'ADMIN']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Талон не найден'}), 404
    
    if ticket.status != 'CALLED':
        return jsonify({'error': 'Талон не был вызван'}), 400
    
    # Обновляем статус
    ticket.status = 'SERVED'
    ticket.ended_at = datetime.utcnow()
    
    # Логируем событие
    event = EventLog(
        event_type='TICKET_SERVED',
        ticket_id=ticket.id,
        actor_id=user_id
    )
    db.session.add(event)
    db.session.commit()
    
    return jsonify({
        'message': 'Прием завершен',
        'ticket_id': ticket.id,
        'status': ticket.status,
        'ended_at': ticket.ended_at.isoformat()
    }), 200

@operator_bp.route('/api/operator/tickets/<int:ticket_id>/no_show', methods=['POST'])
@jwt_required()
def mark_no_show(ticket_id):
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role not in ['OPERATOR', 'ADMIN']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'error': 'Талон не найден'}), 404
    
    if ticket.status != 'CALLED':
        return jsonify({'error': 'Талон не был вызван'}), 400
    
    # Обновляем статус
    ticket.status = 'NO_SHOW'
    ticket.ended_at = datetime.utcnow()
    
    # Логируем событие
    event = EventLog(
        event_type='TICKET_NO_SHOW',
        ticket_id=ticket.id,
        actor_id=user_id
    )
    db.session.add(event)
    db.session.commit()
    
    return jsonify({
        'message': 'Отмечена неявка',
        'ticket_id': ticket.id,
        'status': ticket.status,
        'ended_at': ticket.ended_at.isoformat()
    }), 200

@operator_bp.route('/api/operator/queue', methods=['GET'])
@jwt_required()
def get_queue():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role not in ['OPERATOR', 'ADMIN']:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    # Получаем текущую очередь
    waiting_tickets = Ticket.query.filter_by(status='WAITING').order_by(
        Ticket.created_at.asc()
    ).all()
    
    called_tickets = Ticket.query.filter_by(status='CALLED').all()
    
    result = {
        'waiting': [],
        'called': []
    }
    
    for ticket in waiting_tickets:
        result['waiting'].append({
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'service_name': ticket.service.name,
            'created_at': ticket.created_at.isoformat(),
            'waiting_time_min': int((datetime.utcnow() - ticket.created_at).total_seconds() / 60)
        })
    
    for ticket in called_tickets:
        result['called'].append({
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'service_name': ticket.service.name,
            'called_at': ticket.called_at.isoformat(),
            'operator_id': ticket.operator_id,
            'window_id': ticket.window_id
        })
    
    return jsonify(result), 200