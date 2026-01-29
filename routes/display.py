from flask import Blueprint, jsonify
from models import db, Ticket, Window

display_bp = Blueprint('display', __name__)

@display_bp.route('/api/display/state', methods=['GET'])
def get_display_state():
    """Получение состояния для отображения на табло"""
    
    # Получаем текущий вызванный талон для каждого окна
    windows = Window.query.all()
    display_data = []
    
    for window in windows:
        # Ищем талон в статусе CALLED для этого окна
        current_ticket = Ticket.query.filter_by(
            window_id=window.id,
            status='CALLED'
        ).order_by(Ticket.called_at.desc()).first()
        
        if current_ticket:
            display_data.append({
                'window_id': window.id,
                'window_name': window.name,
                'ticket_number': current_ticket.ticket_number,
                'service_name': current_ticket.service.name,
                'called_at': current_ticket.called_at.isoformat()
            })
        else:
            display_data.append({
                'window_id': window.id,
                'window_name': window.name,
                'ticket_number': '---',
                'service_name': 'Ожидание',
                'called_at': None
            })
    
    # Получаем следующих в очереди (первые 5)
    next_tickets = Ticket.query.filter_by(status='WAITING').order_by(
        Ticket.created_at.asc()
    ).limit(5).all()
    
    next_queue = []
    for ticket in next_tickets:
        next_queue.append({
            'ticket_number': ticket.ticket_number,
            'service_name': ticket.service.name
        })
    
    return jsonify({
        'windows': display_data,
        'next_queue': next_queue,
        'last_updated': db.func.now()
    }), 200

@display_bp.route('/api/display/stats', methods=['GET'])
def get_display_stats():
    """Получение статистики для табло"""
    
    from datetime import datetime, timedelta
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Статистика за сегодня
    total_tickets = Ticket.query.filter(
        Ticket.created_at >= today_start
    ).count()
    
    served_tickets = Ticket.query.filter(
        Ticket.created_at >= today_start,
        Ticket.status == 'SERVED'
    ).count()
    
    waiting_tickets = Ticket.query.filter(
        Ticket.status == 'WAITING'
    ).count()
    
    avg_waiting_time = db.session.query(
        db.func.avg(db.func.extract('epoch', Ticket.called_at - Ticket.created_at) / 60)
    ).filter(
        Ticket.status == 'SERVED',
        Ticket.called_at.isnot(None),
        Ticket.created_at >= today_start
    ).scalar()
    
    return jsonify({
        'today': {
            'total_tickets': total_tickets,
            'served_tickets': served_tickets,
            'waiting_tickets': waiting_tickets,
            'avg_waiting_time_min': round(avg_waiting_time, 1) if avg_waiting_time else 0
        },
        'current_time': datetime.utcnow().isoformat()
    }), 200