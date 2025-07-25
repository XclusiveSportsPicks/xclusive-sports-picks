# backend/app.py

import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas

from models import db, Pick
from scraper import run_scraper, schedule_jobs

# App & config
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI']    = os.getenv('DATABASE_URL', 'sqlite:///instance/picks.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY']             = os.getenv('JWT_SECRET_KEY', 'devkey')

CORS(app)
db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

with app.app_context():
    db.create_all()

@app.route('/ping')
def ping():
    return 'pong', 200

@app.route('/api/login', methods=['POST'])
def login():
    creds = request.json or {}
    if creds.get('username')=='admin' and creds.get('password')=='password':
        return jsonify(access_token=create_access_token(identity='admin'))
    return jsonify(msg='Bad credentials'), 401

@app.route('/api/scrape-now', methods=['GET'])
@jwt_required()
def manual_scrape():
    return jsonify(run_scraper()), 200

@app.route('/api/todays-picks', methods=['GET'])
def todays_picks():
    picks = Pick.query.all()
    return jsonify([p.to_dict() for p in picks])

@app.route('/api/picks', methods=['POST'])
@jwt_required()
def create_pick():
    data = request.json or {}
    pick = Pick(**data)
    db.session.add(pick); db.session.commit()
    return jsonify(id=pick.id), 201

@app.route('/api/picks/<int:pk>', methods=['PUT','DELETE'])
@jwt_required()
def modify_pick(pk):
    pick = Pick.query.get_or_404(pk)
    if request.method=='PUT':
        for k,v in (request.json or {}).items():
            setattr(pick, k, v)
        db.session.commit()
        return jsonify(status='updated')
    db.session.delete(pick); db.session.commit()
    return jsonify(status='deleted')

@app.route('/api/export/csv', methods=['GET'])
@jwt_required()
def export_csv():
    df = pd.DataFrame([p.to_dict() for p in Pick.query.all()])
    buf = BytesIO(); df.to_csv(buf, index=False); buf.seek(0)
    return send_file(buf, mimetype='text/csv', as_attachment=True, download_name='picks.csv')

@app.route('/api/export/pdf', methods=['GET'])
@jwt_required()
def export_pdf():
    picks = [p.to_dict() for p in Pick.query.all()]
    buf = BytesIO(); c = canvas.Canvas(buf); y = 800
    for p in picks:
        line = f"{p['matchup']} | {p['type']} | C:{p['confidence_score']} | W:{p['win_probability']} | {p.get('summary','')}"
        c.drawString(50, y, line); y -= 15
        if y < 50: c.showPage(); y = 800
    c.save(); buf.seek(0)
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name='picks.pdf')

if __name__ == '__main__':
    schedule_jobs(app)
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint:20s} -> {rule.rule}")
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
