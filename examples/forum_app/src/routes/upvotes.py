from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///votes.db'
db = SQLAlchemy(app)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    post_id = db.Column(db.Integer, nullable=False)

@app.route('/vote/upvote/<int:post_id>', methods=['POST'])
def upvote(post_id):
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID is required'}), 400

    existing_vote = Vote.query.filter_by(user_id=user_id, post_id=post_id).first()
    if existing_vote:
        return jsonify({'error': 'You have already voted for this post'}), 400

    new_vote = Vote(user_id=user_id, post_id=post_id)
    db.session.add(new_vote)
    db.session.commit()

    return jsonify({'message': 'Vote recorded successfully'}), 201

if __name__ == '__main__':
    app.run(debug=True)