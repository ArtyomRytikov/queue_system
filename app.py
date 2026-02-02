from flask import Flask, jsonify, render_template
from datetime import time
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import Config
from models import db, Service, Window, Schedule

# Импорт Blueprints
from routes.auth import auth_bp
from routes.tickets import tickets_bp
from routes.operator import operator_bp
from routes.admin import admin_bp
from routes.display import display_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Инициализация расширений
    db.init_app(app)
    jwt = JWTManager(app)
    CORS(app)
    
    # Регистрация Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(operator_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(display_bp)
    
    # Создание таблиц при первом запуске
    with app.app_context():
        db.create_all()
        if Service.query.count() == 0:
            db.session.add_all([
                Service(name='Справка об обучении', avg_service_time_min=5),
                Service(name='Академический отпуск', avg_service_time_min=15),
                Service(name='Пересдача экзамена', avg_service_time_min=10),
                Service(name='Консультация', avg_service_time_min=20),
            ])
        if Window.query.count() == 0:
            db.session.add_all([
                Window(name='Окно 1'),
                Window(name='Окно 2'),
                Window(name='Окно 3'),
            ])
        if Schedule.query.count() == 0:
            db.session.add_all([
                Schedule(day_of_week=1, time_from=time(9, 0), time_to=time(17, 0)),
                Schedule(day_of_week=2, time_from=time(9, 0), time_to=time(17, 0)),
                Schedule(day_of_week=3, time_from=time(9, 0), time_to=time(17, 0)),
                Schedule(day_of_week=4, time_from=time(9, 0), time_to=time(17, 0)),
                Schedule(day_of_week=5, time_from=time(9, 0), time_to=time(16, 0)),
            ])
        db.session.commit()
    
    # Обработчик ошибок
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Ресурс не найден'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
    
    # Корневой маршрут для отображения HTML-страницы
    @app.route('/')
    def index():
        return render_template('index.html')  # Рендерим HTML-шаблон

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
